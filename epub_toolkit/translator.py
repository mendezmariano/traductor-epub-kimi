"""Motor de traducción genérico para EPUBs.

Soporta:
- Dummy (pruebas)
- LibreTranslate (API REST)
- OpenAI / compatibles (API REST)
- Ollama (LLM local via API REST)

A partir de ahora la traducción se realiza por lotes agrupados por archivo
XHTML, lo que mejora la coherencia terminológica y reduce el número de
llamadas a la API.
"""

from __future__ import annotations

import importlib.util
import json
import re
import time
import urllib.error
import urllib.request
import warnings
from abc import ABC, abstractmethod
from typing import Any

from .models import ExtractedDocument, ExtractedFile, TranslationUnit
from .utils import split_text_with_placeholders


# Glosario: término en idioma origen -> término en idioma destino.
Glossary = dict[str, str]


# Patrón de placeholders usado por el extractor.
_PLACEHOLDER_RE = re.compile(r"\{ph(\d+)\}")
# Patrón de marcadores de protección que enviamos al servicio de traducción.
_PROTECTION_RE = re.compile(r"___PH(\d+)___")
_GLOSSARY_RE = re.compile(r"___GLS(\d+)___")


def _protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    """Reemplaza {phN} por marcadores que un traductor no suela modificar.

    Devuelve el texto protegido y un mapa {marcador: placeholder_original}.
    """
    mapping: dict[str, str] = {}

    def repl(m: re.Match[str]) -> str:
        ph = m.group(0)
        marker = f"___PH{m.group(1)}___"
        mapping[marker] = ph
        return marker

    protected = _PLACEHOLDER_RE.sub(repl, text)
    return protected, mapping


def _restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    """Restaura los placeholders originales a partir de los marcadores."""
    text = re.sub(r"___\s*PH\s*(\d+)\s*___", r"___PH\1___", text)
    for marker, ph in mapping.items():
        text = text.replace(marker, ph)
    return text


def _protect_glossary(text: str, glossary: Glossary) -> tuple[str, dict[str, str]]:
    """Reemplaza términos del glosario por marcadores protegidos.

    Ordena los términos de más largo a más corto para evitar reemplazos
    parciales. Devuelve el texto protegido y un mapa {marcador: traducción}.
    """
    if not glossary:
        return text, {}

    mapping: dict[str, str] = {}
    # Escapar caracteres especiales de regex para los términos.
    terms = sorted(glossary.items(), key=lambda kv: len(kv[0]), reverse=True)
    for idx, (term, translation) in enumerate(terms):
        marker = f"___GLS{idx}___"
        mapping[marker] = translation
        escaped = re.escape(term)
        # Reemplazo con regex case-insensitive para mayor robustez.
        text = re.sub(rf"\b{escaped}\b", marker, text, flags=re.IGNORECASE)
    return text, mapping


def _restore_glossary(text: str, mapping: dict[str, str]) -> str:
    """Restaura los términos del glosario ya traducidos."""
    text = re.sub(r"___\s*GLS\s*(\d+)\s*___", r"___GLS\1___", text)
    for marker, translation in mapping.items():
        text = text.replace(marker, translation)
    return text


def _format_glossary(glossary: Glossary) -> str:
    """Formatea el glosario para incluirlo en un prompt."""
    if not glossary:
        return ""
    lines = "\n".join(f"  {term} -> {translation}" for term, translation in glossary.items())
    return f"\nUsa obligatoriamente el siguiente glosario de términos técnicos:\n{lines}\n"


def _apply_glossary(text: str, glossary: Glossary) -> str:
    """Aplica un glosario reemplazando términos directamente.

    Ordena los términos de más largo a más corto para evitar reemplazos
    parciales. Respeta límites de palabra y es insensible a mayúsculas/minúsculas.
    """
    if not glossary:
        return text
    for term, translation in sorted(glossary.items(), key=lambda kv: len(kv[0]), reverse=True):
        escaped = re.escape(term)
        text = re.sub(rf"\b{escaped}\b", translation, text, flags=re.IGNORECASE)
    return text


def _segment_texts(texts: list[str]) -> tuple[list[str], list[list[tuple[str | None, int, bool, bool]]]]:
    """Divide textos con placeholders en segmentos planos y metadatos.

    Devuelve:
      - plain_segments: lista de segmentos de texto plano (sin placeholders ni
        espacios adyacentes a placeholders).
      - unit_segments: lista paralela a `texts`; cada elemento es una lista de
        tuplas (placeholder_id, index_in_plain_segments, left_space, right_space).
        Si placeholder_id es None, el segmento plano está en plain_segments[index].
        left_space/right_space indican si debe haber un espacio a los lados de
        un placeholder, de modo que el reconstructor lo coloque fuera del tag.
    """
    plain_segments: list[str] = []
    unit_segments: list[list[tuple[str | None, int, bool, bool]]] = []
    for text in texts:
        info: list[tuple[str | None, int, bool, bool]] = []
        for part, ph in split_text_with_placeholders(text):
            leading = bool(part) and part[0].isspace()
            trailing = bool(part) and part[-1].isspace()
            cleaned = part.strip()
            if ph is None:
                idx = len(plain_segments)
                plain_segments.append(cleaned)
                info.append((None, idx, leading, trailing))
            else:
                info.append((ph, -1, leading, trailing))

        # Transferir espacios de segmentos planos a placeholders adyacentes,
        # para que los espacios se reconstruyan fuera del tag inline.
        for i in range(len(info)):
            ph, idx, leading, trailing = info[i]
            if ph is None:
                if leading and i > 0 and info[i - 1][0] is not None:
                    prev = info[i - 1]
                    info[i - 1] = (prev[0], prev[1], prev[2], True)
                    info[i] = (ph, idx, False, trailing)
                    leading = False
                if trailing and i < len(info) - 1 and info[i + 1][0] is not None:
                    nxt = info[i + 1]
                    info[i + 1] = (nxt[0], nxt[1], True, nxt[3])
                    info[i] = (ph, idx, leading, False)
        unit_segments.append(info)
    return plain_segments, unit_segments


def _rebuild_texts(plain_translated: list[str],
                   unit_segments: list[list[tuple[str | None, int, bool, bool]]]) -> list[str]:
    """Reconstruye los textos a partir de segmentos traducidos y metadatos."""
    results: list[str] = []
    for info in unit_segments:
        parts: list[str] = []
        for ph, idx, left_space, right_space in info:
            if left_space:
                parts.append(" ")
            if ph is None:
                parts.append(plain_translated[idx])
            else:
                parts.append(ph)
            if right_space:
                parts.append(" ")
        results.append("".join(parts))
    return results


def _translate_plain_segments(translator: Translator,
                              segments: list[str],
                              source_lang: str,
                              target_lang: str,
                              batch_size: int = 100) -> list[str]:
    """Traduce una lista de segmentos planos en lotes."""
    if not segments:
        return []

    translated: list[str] = [""] * len(segments)
    # Agrupar índices de segmentos no vacíos para no enviar strings vacíos.
    non_empty: list[int] = [i for i, s in enumerate(segments) if s]

    for start in range(0, len(non_empty), batch_size):
        batch_indices = non_empty[start:start + batch_size]
        batch = [segments[i] for i in batch_indices]
        try:
            batch_translated = translator.translate_batch(
                batch, source_lang, target_lang
            )
        except NotImplementedError:
            batch_translated = _translate_batch_fallback(
                translator, batch, source_lang, target_lang
            )
        if len(batch_translated) != len(batch):
            raise RuntimeError(
                f"El traductor devolvió {len(batch_translated)} textos para"
                f" {len(batch)} segmentos"
            )
        for idx, text in zip(batch_indices, batch_translated):
            translated[idx] = text

    return translated


def _clean_translated_text(text: str) -> str:
    """Limpia espacios extra que algunos servicios introducen."""
    return re.sub(r"[ \t]+", " ", text).strip()


def _collect_placeholder_ids(text: str) -> set[str]:
    """Devuelve el conjunto de placeholders {phN} presentes en un texto."""
    return set(_PLACEHOLDER_RE.findall(text))


def _validate_translated_texts(originals: list[str],
                               translations: list[str]) -> list[str | None]:
    """Verifica que cada traducción conserve los placeholders del original.

    Devuelve una lista del mismo tamaño que `translations`: el texto validado
    si los placeholders coinciden, o `None` si se detectó una pérdida.
    """
    validated: list[str | None] = []
    for original, translation in zip(originals, translations):
        original_ids = _collect_placeholder_ids(original)
        translated_ids = _collect_placeholder_ids(translation)
        if original_ids and original_ids != translated_ids:
            validated.append(None)
        else:
            validated.append(translation)
    return validated


def _system_prompt(source_lang: str, target_lang: str,
                   expansion_hint: float | None = None,
                   glossary: Glossary | None = None,
                   strict: bool = False) -> str:
    """Prompt de sistema para traductores basados en LLM."""
    expansion = ""
    if expansion_hint and expansion_hint > 1.0:
        pct = int((expansion_hint - 1) * 100)
        expansion = (
            f" El {target_lang} suele ser aproximadamente un {pct}% más largo"
            f" que el {source_lang}; mantén una longitud similar sin omitir"
            " contenido."
        )
    glossary_text = _format_glossary(glossary or {})
    strict_clause = (
        " Es CRÍTICO que conserves TODOS los marcadores ___PHN___ exactamente"
        " como aparecen en el texto. Si omites alguno, la traducción será"
        " inválida."
        if strict
        else ""
    )
    return (
        f"Eres un traductor profesional. Traduce el texto del {source_lang} al"
        f" {target_lang}. NO traduzcas ni modifiques los marcadores de la forma"
        f" {{ph0}}, {{ph1}}, etc. ni ___PH0___, ___PH1___, etc. ni"
        f" ___GLS0___, ___GLS1___, etc. Conserva la puntuación, el formato y"
        f" los espacios.{expansion}{glossary_text}{strict_clause} Responde"
        " ÚNICAMENTE con la traducción, sin explicaciones ni markdown."
    )


def _batch_prompt(texts: list[str], source_lang: str, target_lang: str,
                  context_title: str = "",
                  expansion_hint: float | None = None,
                  glossary: Glossary | None = None,
                  strict: bool = False) -> str:
    """Prompt para traducir un lote de textos numerados."""
    base = _system_prompt(source_lang, target_lang, expansion_hint, glossary, strict)
    context = f"\nContexto: capítulo/sección '{context_title}'." if context_title else ""
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))
    return (
        f"{base}{context}\n\n"
        "Traduce cada texto numerado. Responde ÚNICAMENTE con la misma cantidad"
        " de líneas, una traducción por línea, precedida por su número y un punto."
        " No agrupes ni combines líneas.\n\n"
        f"{lines}\n\n"
        "Traducciones:"
    )


def _parse_numbered_translations(response: str, expected: int) -> list[str]:
    """Extrae traducciones numeradas de la respuesta de un LLM.

    Soporta formatos como:
      1. Hola mundo
      1) Hola mundo
    Si falla el parseo, devuelve una lista vacía para forzar fallback.
    """
    results: list[str | None] = [None] * expected
    pattern = re.compile(r"^\s*(\d+)[.\)]\s*(.*)$", re.MULTILINE)
    for match in pattern.finditer(response):
        idx = int(match.group(1)) - 1
        if 0 <= idx < expected:
            results[idx] = match.group(2).strip()

    # Si no se parseó ninguna línea, intentar dividir por líneas limpias.
    if all(r is None for r in results):
        lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
        if len(lines) == expected:
            return lines
        return []

    return [r if r is not None else "" for r in results]


def _translate_batch_fallback(translator: Translator, texts: list[str],
                              source_lang: str, target_lang: str) -> list[str]:
    """Fallback: traduce uno a uno si el motor no soporta lotes."""
    return [translator.translate(t, source_lang, target_lang) for t in texts]


def translate_unit(translator: Translator, unit: TranslationUnit,
                   source_lang: str, target_lang: str,
                   glossary: Glossary | None = None) -> str:
    """Traduce una única unidad preservando placeholders y glosario."""
    file = ExtractedFile(path="", units=[unit])
    results = translate_batch_for_file(translator, file, source_lang, target_lang, glossary)
    return results[0] if results else unit.original


def _translate_and_validate(translator: Translator,
                            protected_texts: list[str],
                            originals: list[str],
                            ph_mappings: list[dict[str, str]],
                            glossary_mappings: list[dict[str, str]],
                            source_lang: str, target_lang: str,
                            context_title: str,
                            labels: list[str],
                            strict_retry: bool = True) -> list[str]:
    """Traduce un lote, valida placeholders y aplica fallback si es necesario.

    `labels` se usa únicamente para emitir advertencias identificables.
    """
    try:
        translated = translator.translate_batch(
            protected_texts, source_lang, target_lang,
            context_title=context_title,
        )
    except NotImplementedError:
        translated = _translate_batch_fallback(
            translator, protected_texts, source_lang, target_lang
        )

    if len(translated) != len(originals):
        raise RuntimeError(
            f"El traductor devolvió {len(translated)} textos para"
            f" {len(originals)} textos"
        )

    restored = [
        _restore_glossary(_restore_placeholders(t, ph_map), glossary_map)
        for t, ph_map, glossary_map in zip(translated, ph_mappings, glossary_mappings)
    ]
    validated = _validate_translated_texts(originals, restored)

    results: list[str] = []
    for idx, valid in enumerate(validated):
        if valid is not None:
            results.append(_clean_translated_text(valid))
            continue

        missing = _collect_placeholder_ids(originals[idx]) - _collect_placeholder_ids(restored[idx])
        if strict_retry:
            try:
                retry = translator.translate_batch(
                    [protected_texts[idx]], source_lang, target_lang,
                    context_title=context_title,
                    strict=True,
                )[0]
            except NotImplementedError:
                retry = translator.translate(
                    protected_texts[idx], source_lang, target_lang
                )
            retry_restored = _restore_glossary(
                _restore_placeholders(retry, ph_mappings[idx]),
                glossary_mappings[idx],
            )
            if _collect_placeholder_ids(originals[idx]) == _collect_placeholder_ids(retry_restored):
                results.append(_clean_translated_text(retry_restored))
                continue

        warnings.warn(
            f"Placeholder(s) {missing} perdido(s) en {labels[idx]};"
            f" se conserva el texto original.",
            UserWarning,
            stacklevel=3,
        )
        results.append(_clean_translated_text(originals[idx]))

    return results


def translate_batch_for_file(translator: Translator, file: ExtractedFile,
                             source_lang: str, target_lang: str,
                             glossary: Glossary | None = None) -> list[str]:
    """Traduce todas las unidades de un archivo preservando placeholders y glosario."""
    units = [u for u in file.units if u.translatable]
    if not units:
        return []

    if getattr(translator, "segment_placeholders", False):
        return _translate_batch_for_file_segmented(
            translator, file, units, source_lang, target_lang, glossary
        )

    protected_texts: list[str] = []
    ph_mappings: list[dict[str, str]] = []
    glossary_mappings: list[dict[str, str]] = []
    originals: list[str] = []
    labels: list[str] = []
    for unit in units:
        # 1. Proteger términos del glosario (texto original -> marcador).
        text, glossary_mapping = _protect_glossary(unit.original, glossary or {})
        # 2. Proteger placeholders inline.
        protected, ph_mapping = _protect_placeholders(text)
        protected_texts.append(protected)
        ph_mappings.append(ph_mapping)
        glossary_mappings.append(glossary_mapping)
        originals.append(unit.original)
        labels.append(f"{file.path}::{unit.unit_id}")

    return _translate_and_validate(
        translator, protected_texts, originals, ph_mappings, glossary_mappings,
        source_lang, target_lang, file.context_title, labels,
    )


def _translate_batch_for_file_segmented(translator: Translator,
                                        file: ExtractedFile,
                                        units: list[TranslationUnit],
                                        source_lang: str,
                                        target_lang: str,
                                        glossary: Glossary | None = None) -> list[str]:
    """Traduce un archivo segmentando por placeholders.

    Separa el texto plano de los placeholders, traduce los segmentos planos en
    lotes y reconstruye cada unidad con los placeholders originales. Aplica el
    glosario después de reconstruir para evitar enviar marcadores al servicio.
    """
    originals = [u.original for u in units]
    plain_segments, unit_segments = _segment_texts(originals)
    translated_segments = _translate_plain_segments(
        translator, plain_segments, source_lang, target_lang
    )
    results = _rebuild_texts(translated_segments, unit_segments)

    if glossary:
        results = [_apply_glossary(t, glossary) for t in results]

    return [_clean_translated_text(t) for t in results]


def _translate_attrs_for_file(translator: Translator, file: ExtractedFile,
                              source_lang: str, target_lang: str,
                              glossary: Glossary | None = None) -> None:
    """Traduce los atributos traducibles de las unidades de un archivo."""
    units = [u for u in file.units if u.translatable]

    attr_entries: list[tuple[TranslationUnit, str, str]] = []
    attr_originals: list[str] = []
    for unit in units:
        for key, attrs in unit.translatable_attrs.items():
            for attr_name, attr_value in attrs.items():
                attr_entries.append((unit, key, attr_name))
                attr_originals.append(attr_value)

    if not attr_originals:
        return

    if getattr(translator, "segment_placeholders", False):
        plain_segments, unit_segments = _segment_texts(attr_originals)
        translated_segments = _translate_plain_segments(
            translator, plain_segments, source_lang, target_lang, batch_size=100
        )
        translated = _rebuild_texts(translated_segments, unit_segments)
        if glossary:
            translated = [_apply_glossary(t, glossary) for t in translated]
        translated = [_clean_translated_text(t) for t in translated]
    else:
        attr_texts: list[str] = []
        attr_ph_mappings: list[dict[str, str]] = []
        attr_glossary_mappings: list[dict[str, str]] = []
        attr_labels: list[str] = []
        for original, (unit, key, attr_name) in zip(attr_originals, attr_entries):
            text, glossary_mapping = _protect_glossary(original, glossary or {})
            protected, ph_mapping = _protect_placeholders(text)
            attr_texts.append(protected)
            attr_ph_mappings.append(ph_mapping)
            attr_glossary_mappings.append(glossary_mapping)
            attr_labels.append(f"{file.path}::{unit.unit_id}@{key}.{attr_name}")

        context = f"Atributos HTML de {file.context_title}" if file.context_title else "Atributos HTML"
        translated = _translate_and_validate(
            translator, attr_texts, attr_originals, attr_ph_mappings,
            attr_glossary_mappings, source_lang, target_lang, context, attr_labels,
        )

    for (unit, key, attr_name), text in zip(attr_entries, translated):
        unit.translated_attrs.setdefault(key, {})[attr_name] = text


def estimate_document(document: ExtractedDocument) -> dict[str, Any]:
    """Estima el volumen de traducción de un documento sin traducirlo.

    Devuelve un diccionario con:
    - total_units: número de unidades traducibles.
    - total_chars: caracteres totales a traducir (texto + atributos).
    - estimated_tokens: estimación aproximada de tokens (chars // 4).
    - files: lista de resúmenes por archivo.
    """
    files: list[dict[str, Any]] = []
    total_units = 0
    total_chars = 0

    for path, extracted_file in document.files.items():
        units = [u for u in extracted_file.units if u.translatable]
        chars = sum(len(u.original) for u in units)
        for u in units:
            for attrs in u.translatable_attrs.values():
                chars += sum(len(v) for v in attrs.values())
        files.append({"path": path, "units": len(units), "chars": chars})
        total_units += len(units)
        total_chars += chars

    return {
        "total_units": total_units,
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 4,
        "files": files,
    }


def translate_document(translator: Translator, document: ExtractedDocument,
                       source_lang: str = "en", target_lang: str = "es",
                       progress: bool = True,
                       glossary: Glossary | None = None) -> None:
    """Traduce todas las unidades de un documento extraído por lotes."""
    files = list(document.files.values())
    total_units = sum(len([u for u in f.units if u.translatable]) for f in files)
    processed = 0

    tqdm_available = progress and importlib.util.find_spec("tqdm") is not None
    pbar: Any | None = None
    if tqdm_available:
        from tqdm import tqdm
        pbar = tqdm(total=total_units, desc="Traduciendo unidades", unit="unidad")

    try:
        for extracted_file in files:
            units = [u for u in extracted_file.units if u.translatable]
            if not units:
                continue

            translations = translate_batch_for_file(
                translator, extracted_file, source_lang, target_lang, glossary
            )

            for unit, translation in zip(units, translations):
                unit.translation = translation
                processed += 1
                if pbar is not None:
                    pbar.update(1)
                elif progress:
                    print(f"  [{processed}/{total_units}] {unit.unit_id} ({extracted_file.path})")

            _translate_attrs_for_file(
                translator, extracted_file, source_lang, target_lang, glossary
            )
    finally:
        if pbar is not None:
            pbar.close()


class Translator(ABC):
    """Interfaz base para motores de traducción."""

    # Si es True, el pipeline traduce segmentos de texto plano separando los
    # placeholders, evitando que el servicio modifique los marcadores.
    segment_placeholders: bool = False

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Traduce un texto del idioma origen al destino."""
        ...

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: Glossary | None = None,
                        **kwargs: Any) -> list[str]:
        """Traduce un lote de textos.

        Los motores pueden sobreescribir este método para enviar lotes a la API.
        Por defecto se traduce uno a uno.
        """
        return _translate_batch_fallback(self, texts, source_lang, target_lang)


class DummyTranslator(Translator):
    """Traductor de prueba: marca el texto como traducido y lo expande."""

    def __init__(self, expansion: float = 1.25,
                 expansion_hint: float | None = None) -> None:
        self.expansion = expansion_hint if expansion_hint is not None else expansion

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        marker = f"[{target_lang.upper()}]"
        repeats = max(1, int(self.expansion))
        middle = text if repeats == 1 else f"{text} {' '.join([text] * (repeats - 1))}"
        return f"{marker} {middle} {marker}"

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: Glossary | None = None,
                        **kwargs: Any) -> list[str]:
        return [self.translate(t, source_lang, target_lang) for t in texts]


class LibreTranslateTranslator(Translator):
    """Traductor mediante una instancia de LibreTranslate (local o pública)."""

    # LibreTranslate tiende a modificar o eliminar marcadores de placeholders.
    # Usamos segmentación para preservar el marcado inline.
    segment_placeholders = True

    def __init__(self, base_url: str = "https://libretranslate.de",
                 api_key: str | None = None,
                 delay: float = 0.0,
                 expansion_hint: float | None = None,
                 retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.delay = delay
        self.retries = retries
        # expansion_hint se acepta por consistencia; no se utiliza directamente.

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        results = self._translate_batch([text], source_lang, target_lang)
        return results[0]

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: Glossary | None = None,
                        **kwargs: Any) -> list[str]:
        # LibreTranslate no usa directamente el glosario; los términos ya se
        # protegen con marcadores ___GLS___ en translate_batch_for_file.
        return self._translate_batch(texts, source_lang, target_lang)

    def _translate_batch(self, texts: list[str], source_lang: str,
                         target_lang: str) -> list[str]:
        url = f"{self.base_url}/translate"
        payload: dict[str, Any] = {
            "q": texts,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        if self.api_key:
            payload["api_key"] = self.api_key

        result = _post_json_with_retry(url, payload, retries=self.retries)
        translated = result.get("translatedText")
        if translated is None:
            raise RuntimeError(
                f"Respuesta inesperada de LibreTranslate (falta translatedText): {result}"
            )

        # LibreTranslate puede devolver una lista o un string según la entrada.
        if isinstance(translated, list):
            texts_out = translated
        else:
            texts_out = [translated]

        if len(texts_out) != len(texts):
            raise RuntimeError(
                f"LibreTranslate devolvió {len(texts_out)} textos para {len(texts)}"
            )
        if self.delay:
            time.sleep(self.delay)
        return texts_out


class OpenAICompatibleTranslator(Translator):
    """Traductor mediante API de chat completions (OpenAI, Groq, Mistral, etc.)."""

    def __init__(self, api_key: str,
                 base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o-mini",
                 temperature: float = 0.3,
                 expansion_hint: float | None = None,
                 retries: int = 3) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.expansion_hint = expansion_hint
        self.retries = retries

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        results = self.translate_batch([text], source_lang, target_lang)
        return results[0]

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: Glossary | None = None,
                        **kwargs: Any) -> list[str]:
        if not texts:
            return []
        strict = kwargs.get("strict", False)
        prompt = _batch_prompt(
            texts, source_lang, target_lang, context_title, self.expansion_hint, glossary, strict
        )
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": _system_prompt(source_lang, target_lang, self.expansion_hint, glossary, strict)},
                {"role": "user", "content": prompt},
            ],
        }
        result = _post_json_with_retry(
            url, payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            retries=self.retries,
        )
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Respuesta inesperada de la API: {result}") from e

        parsed = _parse_numbered_translations(content, len(texts))
        if not parsed:
            # Fallback: si el LLM no respeta el formato, traducimos uno a uno.
            return _translate_batch_fallback(self, texts, source_lang, target_lang)
        return parsed


# Alias para compatibilidad con versiones anteriores.
OpenAITranslator = OpenAICompatibleTranslator


class OllamaTranslator(Translator):
    """Traductor mediante Ollama ejecutándose localmente."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "llama3.2",
                 temperature: float = 0.3,
                 expansion_hint: float | None = None,
                 retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.expansion_hint = expansion_hint
        self.retries = retries

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        results = self.translate_batch([text], source_lang, target_lang)
        return results[0]

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: Glossary | None = None,
                        **kwargs: Any) -> list[str]:
        if not texts:
            return []
        strict = kwargs.get("strict", False)
        prompt = _batch_prompt(
            texts, source_lang, target_lang, context_title, self.expansion_hint, glossary, strict
        )
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        result = _post_json_with_retry(url, payload, retries=self.retries)
        if "response" not in result:
            raise RuntimeError(f"Respuesta inesperada de Ollama: {result}")

        parsed = _parse_numbered_translations(result["response"], len(texts))
        if not parsed:
            return _translate_batch_fallback(self, texts, source_lang, target_lang)
        return parsed


def _post_json_raw(url: str, payload: dict[str, Any],
                   headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Envía un POST JSON y devuelve la respuesta parseada sin envolver excepciones."""
    data = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")

    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any],
               headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Envía un POST JSON y devuelve la respuesta parseada."""
    try:
        return _post_json_raw(url, payload, headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Error HTTP ({e.code}): {body}") from e
    except Exception as e:
        raise RuntimeError(f"No se pudo contactar el servicio: {e}") from e


def _is_retryable_http_error(code: int) -> bool:
    """Determina si un código HTTP amerita reintento."""
    return code >= 500 or code == 429


def _post_json_with_retry(url: str, payload: dict[str, Any],
                          headers: dict[str, str] | None = None,
                          retries: int = 3,
                          base_delay: float = 1.0) -> dict[str, Any]:
    """Envía un POST JSON con reintentros exponenciales ante errores transitorios."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return _post_json_raw(url, payload, headers)
        except urllib.error.HTTPError as e:
            last_error = e
            body = e.read().decode("utf-8", errors="ignore")
            if not _is_retryable_http_error(e.code) or attempt == retries:
                raise RuntimeError(f"Error HTTP ({e.code}): {body}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            if attempt == retries:
                raise RuntimeError(f"No se pudo contactar el servicio: {e}") from e
        except Exception as e:
            raise RuntimeError(f"No se pudo contactar el servicio: {e}") from e

        time.sleep(base_delay * (2 ** attempt))

    raise RuntimeError(f"No se pudo contactar el servicio tras {retries} reintentos: {last_error}")


def create_translator(engine: str, **kwargs) -> Translator:
    """Factoría de traductores."""
    engine = engine.lower()
    if engine == "dummy":
        return DummyTranslator(**kwargs)
    if engine == "libretranslate":
        return LibreTranslateTranslator(**kwargs)
    if engine in ("openai", "openai-compatible"):
        return OpenAICompatibleTranslator(**kwargs)
    if engine == "ollama":
        return OllamaTranslator(**kwargs)
    raise ValueError(f"Motor de traducción desconocido: {engine}")
