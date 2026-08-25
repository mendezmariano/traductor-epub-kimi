#!/usr/bin/env python3
"""CLI para descomponer, extraer y reconstruir EPUBs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from epub_toolkit.deconstructor import Deconstructor
from epub_toolkit.extractor import Extractor
from epub_toolkit.models import ExtractedDocument
from epub_toolkit.reconstructor import Reconstructor
from epub_toolkit.translator import create_translator, translate_document


def cmd_deconstruct(args: argparse.Namespace) -> int:
    epub_path = Path(args.epub)
    output_dir = Path(args.output)
    extracted_dir = output_dir / "extracted"

    deconstructor = Deconstructor(epub_path, extracted_dir, clean=True)
    extracted_path, opf_path = deconstructor.deconstruct()
    print(f"Extraído: {extracted_path}")

    extractor = Extractor(extracted_path, opf_path)
    document = extractor.extract(source_epub=epub_path)

    units_path = output_dir / "translation_units.json"
    units_path.parent.mkdir(parents=True, exist_ok=True)
    with open(units_path, "w", encoding="utf-8") as f:
        json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"Unidades de traducción: {units_path}")

    total_units = sum(len(f.units) for f in document.files.values())
    print(f"Total de unidades extraídas: {total_units}")
    return 0


def cmd_reconstruct(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir)
    extracted_dir = work_dir / "extracted"
    units_path = work_dir / "translation_units.json"

    if not extracted_dir.exists():
        print(f"No se encontró directorio extraído: {extracted_dir}", file=sys.stderr)
        return 1
    if not units_path.exists():
        print(f"No se encontró archivo de unidades: {units_path}", file=sys.stderr)
        return 1

    reconstructor = Reconstructor(extracted_dir, units_path)
    output_epub = Path(args.output)
    reconstructor.reconstruct(output_epub, update_language=args.language)
    print(f"EPUB reconstruido: {output_epub}")
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir)
    units_path = work_dir / "translation_units.json"

    if not units_path.exists():
        print(f"No se encontró archivo de unidades: {units_path}", file=sys.stderr)
        return 1

    with open(units_path, "r", encoding="utf-8") as f:
        document = ExtractedDocument.from_dict(json.load(f))

    glossary: dict[str, str] | None = None
    if args.glossary:
        glossary_path = Path(args.glossary)
        if not glossary_path.exists():
            print(f"No se encontró el glosario: {glossary_path}", file=sys.stderr)
            return 1
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)
        if not isinstance(glossary, dict):
            print("El glosario debe ser un JSON de pares termino->traduccion.", file=sys.stderr)
            return 1

    engine_kwargs: dict = {"expansion_hint": args.expansion}
    if args.base_url:
        engine_kwargs["base_url"] = args.base_url
    if args.api_key:
        engine_kwargs["api_key"] = args.api_key
    if args.delay is not None:
        engine_kwargs["delay"] = args.delay
    if args.model:
        engine_kwargs["model"] = args.model
    if args.temperature is not None:
        engine_kwargs["temperature"] = args.temperature

    try:
        translator = create_translator(args.engine, **engine_kwargs)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"Traduciendo con motor '{args.engine}' ({args.source} -> {args.target})...")
    if glossary:
        print(f"Usando glosario con {len(glossary)} términos.")
    translate_document(translator, document, source_lang=args.source,
                       target_lang=args.target, progress=not args.quiet,
                       glossary=glossary)

    with open(units_path, "w", encoding="utf-8") as f:
        json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"Unidades traducidas guardadas en: {units_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Descompón, extrae y reconstruye EPUBs para traducción."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dec = subparsers.add_parser("deconstruct", help="Extrae un EPUB en componentes.")
    dec.add_argument("epub", help="Ruta al EPUB de entrada.")
    dec.add_argument("--output", "-o", required=True,
                     help="Directorio de salida para el EPUB descompuesto.")
    dec.set_defaults(func=cmd_deconstruct)

    rec = subparsers.add_parser("reconstruct", help="Reconstruye un EPUB a partir de un trabajo previo.")
    rec.add_argument("work_dir", help="Directorio de trabajo generado por deconstruct.")
    rec.add_argument("--output", "-o", required=True,
                     help="Ruta del EPUB de salida.")
    rec.add_argument("--language", default=None,
                     help="Actualiza el idioma en el .opf (p.ej. es).")
    rec.set_defaults(func=cmd_reconstruct)

    tr = subparsers.add_parser("translate", help="Traduce las unidades extraídas.")
    tr.add_argument("work_dir", help="Directorio de trabajo generado por deconstruct.")
    tr.add_argument("--engine", default="dummy",
                    choices=["dummy", "libretranslate", "openai", "ollama"],
                    help="Motor de traducción.")
    tr.add_argument("--source", default="en", help="Idioma origen.")
    tr.add_argument("--target", default="es", help="Idioma destino.")
    tr.add_argument("--expansion", type=float, default=1.25,
                    help="Factor de expansión (dummy) o hint para LLMs.")
    tr.add_argument("--base-url", default=None,
                    help="URL base del servicio (LibreTranslate, OpenAI o Ollama).")
    tr.add_argument("--api-key", default=None,
                    help="API key para OpenAI o LibreTranslate.")
    tr.add_argument("--delay", type=float, default=None,
                    help="Segundos de espera entre peticiones (LibreTranslate).")
    tr.add_argument("--model", default=None,
                    help="Modelo para OpenAI u Ollama.")
    tr.add_argument("--temperature", type=float, default=None,
                    help="Temperatura de muestreo para LLMs.")
    tr.add_argument("--glossary", default=None,
                    help="Ruta a un JSON con pares 'término': 'traducción'.")
    tr.add_argument("--quiet", action="store_true",
                    help="No mostrar progreso.")
    tr.set_defaults(func=cmd_translate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
