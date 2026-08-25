"""Extrae unidades de traducción de los XHTML de un EPUB."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from lxml import etree

from .models import ExtractedDocument, ExtractedFile, Placeholder, TranslationUnit
from .utils import (
    BLOCK_TAGS,
    INLINE_TAGS,
    SKIPPED_TAGS,
    VOID_TAGS,
    XHTML_NS,
    clean_text,
    make_placeholder,
    opf_dir,
    parse_xhtml,
    serialize_xhtml,
)


TMP_ID_ATTR = "{http://www.w3.org/1999/xhtml}data-tmp-id"
# Atributo sin namespace para la serialización más limpia.
TMP_ID_ATTR_NO_NS = "data-tmp-id"


def _local_name(element: etree._Element) -> str:
    """Devuelve el nombre local de un tag sin namespace."""
    tag = element.tag
    if isinstance(tag, str):
        return tag.split("}")[-1] if tag.startswith("{") else tag
    return ""


def _is_block(element: etree._Element) -> bool:
    return _local_name(element) in BLOCK_TAGS


def _is_inline(element: etree._Element) -> bool:
    return _local_name(element) in INLINE_TAGS


def _is_skipped(element: etree._Element) -> bool:
    return _local_name(element) in SKIPPED_TAGS


def _is_void(element: etree._Element) -> bool:
    return _local_name(element) in VOID_TAGS


def _is_translation_unit(element: etree._Element) -> bool:
    """Un nodo es unidad si es de bloque, no skipped, contiene texto y sus
    hijos elemento son todos inline."""
    if not _is_block(element) or _is_skipped(element):
        return False

    has_element_children = False
    for child in element:
        has_element_children = True
        if not _is_inline(child):
            return False

    text = "".join(element.itertext())
    return bool(text and text.strip())


def _collect_units(root: etree._Element, counter: Iterator[int]) -> list[TranslationUnit]:
    """Recorre el árbol y recolecta unidades de traducción."""
    units: list[TranslationUnit] = []

    for element in root.iter():
        if _is_skipped(element):
            continue
        if _is_translation_unit(element):
            unit = _unit_from_element(element, counter)
            if unit:
                units.append(unit)
    return units


def _unit_from_element(element: etree._Element,
                       counter: Iterator[int]) -> TranslationUnit | None:
    """Construye una TranslationUnit a partir de un elemento de bloque."""
    text_parts: list[str] = []
    placeholders: dict[str, Placeholder] = {}

    if element.text:
        text_parts.append(clean_text(element.text))

    for child in element:
        if _is_inline(child):
            _extract_inline(child, text_parts, placeholders, counter)
            if child.tail:
                text_parts.append(clean_text(child.tail))
        # Los hijos no inline no deberían aparecer por la definición de unidad.

    original = clean_text("".join(text_parts))
    if not original.strip():
        return None

    unit_id = f"u{next(counter)}"
    # Marcamos el elemento para poder reconstruirlo más tarde.
    element.set(TMP_ID_ATTR_NO_NS, unit_id)

    return TranslationUnit(
        unit_id=unit_id,
        xpath=_stable_xpath(element),
        original=original,
        placeholders=placeholders,
        translatable=True,
        translation=None,
    )


def _extract_inline(element: etree._Element,
                    text_parts: list[str],
                    placeholders: dict[str, Placeholder],
                    counter: Iterator[int]) -> None:
    """Serializa un tag inline como placeholder y recurre sobre sus hijos."""
    ph_id = make_placeholder(next(counter))
    tag = _local_name(element)
    attrs = {k.split("}")[-1] if k.startswith("{") else k: v
             for k, v in element.attrib.items()
             if k != TMP_ID_ATTR and k != TMP_ID_ATTR_NO_NS}

    placeholders[ph_id] = Placeholder(
        tag=tag,
        attrs=attrs,
        self_closing=_is_void(element),
    )

    text_parts.append(ph_id)

    if _is_void(element):
        return

    if element.text:
        text_parts.append(clean_text(element.text))

    for child in element:
        if _is_inline(child):
            _extract_inline(child, text_parts, placeholders, counter)
        else:
            # Si aparece un no-inline anidado inesperado, lo saltamos pero
            # conservamos su texto plano para no perder contenido.
            text_parts.append(clean_text("".join(child.itertext())))

    text_parts.append(ph_id)


def _stable_xpath(element: etree._Element) -> str:
    """Genera un xpath simple basado en posición para referencia humana."""
    path_parts: list[str] = []
    node: etree._Element | None = element
    while node is not None and _local_name(node):
        name = _local_name(node)
        siblings = [s for s in node.itersiblings(preceding=True)
                    if _local_name(s) == name]
        pos = len(siblings) + 1
        path_parts.append(f"{name}[{pos}]")
        node = node.getparent()
    return "/" + "/".join(reversed(path_parts))


def _extract_context_title(root: etree._Element) -> str:
    """Extrae un título representativo del XHTML (h1, h2 o title)."""
    ns = "{http://www.w3.org/1999/xhtml}"

    # 1. Primer h1 o h2 con texto visible (mejor contexto de capítulo).
    for tag in ("h1", "h2"):
        for el in root.iter(f"{ns}{tag}"):
            text = "".join(el.itertext()).strip()
            if text:
                return clean_text(text)

    # 2. <title> dentro de <head> como fallback.
    head = root.find(f"{ns}head")
    if head is not None:
        title = head.find(f"{ns}title")
        if title is not None and title.text:
            return clean_text(title.text)
    return ""


class Extractor:
    """Extrae unidades traducibles de los XHTML de un EPUB descomprimido."""

    def __init__(self, extracted_dir: str | Path, opf_path: str) -> None:
        self.extracted_dir = Path(extracted_dir)
        self.opf_path = opf_path
        self.base_dir = self.extracted_dir / opf_dir(opf_path)

    def extract(self, source_epub: str | Path) -> ExtractedDocument:
        """Genera el documento de extracción con todas las unidades."""
        from .utils import list_xhtml_files

        xhtml_files = list_xhtml_files(self.extracted_dir, self.opf_path)
        files: dict[str, ExtractedFile] = {}
        global_counter = iter(range(1_000_000))

        for href in xhtml_files:
            path = self.base_dir / href
            if not path.exists():
                continue

            tree = parse_xhtml(path)
            root = tree.getroot()
            context_title = _extract_context_title(root)
            units = _collect_units(root, global_counter)
            if units:
                files[href] = ExtractedFile(
                    path=href,
                    units=units,
                    context_title=context_title,
                )
                # Persistimos los data-tmp-id para que el reconstructor pueda
                # localizar cada unidad de forma robusta.
                serialize_xhtml(tree, path)

        return ExtractedDocument(
            source_epub=str(source_epub),
            language="en",
            files=files,
        )
