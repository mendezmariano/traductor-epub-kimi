"""Tests de roundtrip estructural completo para EPUBs de ejemplo.

Descompone cada EPUB de libros/, lo reconstruye sin traducir y compara
la estructura (DOM, CSS y recursos binarios) contra el original.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from epub_toolkit.analyzer import compare_epubs
from epub_toolkit.deconstructor import Deconstructor
from epub_toolkit.extractor import Extractor
from epub_toolkit.reconstructor import Reconstructor


EPUB_DIR = Path(__file__).resolve().parent.parent / "libros"


def _epub_files() -> list[Path]:
    return [p for p in EPUB_DIR.glob("*.epub") if p.is_file()]


class FullRoundtripTestCase(unittest.TestCase):
    """Prueba de roundtrip estructural para cada EPUB de ejemplo."""

    def test_epubs_found(self) -> None:
        if not _epub_files():
            self.skipTest(
                f"No se encontraron EPUBs en {EPUB_DIR};"
                " los tests de roundtrip se omiten en este entorno."
            )
        self.assertTrue(_epub_files())

    def _roundtrip_epub(self, epub_path: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="epub_full_roundtrip_") as tmp:
            tmp_path = Path(tmp)
            work_dir = tmp_path / "work"
            rebuilt_epub = tmp_path / "rebuilt.epub"
            units_path = work_dir / "translation_units.json"

            # 1. Descomponer.
            deconstructor = Deconstructor(epub_path, work_dir / "extracted", clean=True)
            extracted_dir, opf_path = deconstructor.deconstruct()

            # 2. Extraer unidades (sin traducir).
            extractor = Extractor(extracted_dir, opf_path)
            document = extractor.extract(source_epub=epub_path)

            # Guardar units.json para el reconstructor.
            with open(units_path, "w", encoding="utf-8") as f:
                json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)

            # 3. Reconstruir sin aplicar traducciones.
            reconstructor = Reconstructor(extracted_dir, units_path)
            reconstructor.reconstruct(rebuilt_epub)

            # 4. Comparar estructuralmente.
            report = compare_epubs(epub_path, rebuilt_epub)

            if not report["equivalent"]:
                self.fail(
                    f"Diferencias estructurales detectadas en {epub_path.name}:\n"
                    f"{json.dumps(report['differences'], indent=2, ensure_ascii=False)}"
                )

    def test_full_roundtrip(self) -> None:
        epub_files = _epub_files()
        if not epub_files:
            self.skipTest(
                f"No se encontraron EPUBs en {EPUB_DIR};"
                " los tests de roundtrip se omiten en este entorno."
            )
        for epub_path in epub_files:
            with self.subTest(epub=epub_path.name):
                self._roundtrip_epub(epub_path)


if __name__ == "__main__":
    unittest.main()
