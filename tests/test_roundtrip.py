"""Tests de roundtrip: descomponer y reconstruir EPUBs sin perder validez."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

from epub_toolkit.deconstructor import Deconstructor
from epub_toolkit.extractor import Extractor
from epub_toolkit.reconstructor import Reconstructor
from epub_toolkit.utils import find_opf_path, list_xhtml_files, package_epub


EPUB_DIR = Path(__file__).resolve().parent.parent / "libros"


def _epub_files() -> list[Path]:
    return [p for p in EPUB_DIR.glob("*.epub") if p.is_file()]


class RoundtripTestCase(unittest.TestCase):
    """Prueba de roundtrip para cada EPUB de ejemplo."""

    def test_epubs_found(self) -> None:
        self.assertTrue(_epub_files(), f"No se encontraron EPUBs en {EPUB_DIR}")

    def _roundtrip_epub(self, epub_path: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="epub_roundtrip_") as tmp:
            tmp_path = Path(tmp)
            work_dir = tmp_path / "work"
            rebuilt_epub = tmp_path / "rebuilt.epub"

            deconstructor = Deconstructor(epub_path, work_dir / "extracted", clean=True)
            extracted_dir, opf_path = deconstructor.deconstruct()

            extractor = Extractor(extracted_dir, opf_path)
            document = extractor.extract(source_epub=epub_path)
            units_path = work_dir / "translation_units.json"
            with open(units_path, "w", encoding="utf-8") as f:
                json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)

            total_units = sum(len(f.units) for f in document.files.values())
            self.assertGreater(total_units, 0,
                               f"No se extrajeron unidades de {epub_path.name}")

            reconstructor = Reconstructor(extracted_dir, units_path)
            reconstructor.reconstruct(rebuilt_epub)

            self.assertTrue(rebuilt_epub.exists())
            self.assertTrue(zipfile.is_zipfile(rebuilt_epub))

            with zipfile.ZipFile(rebuilt_epub, "r") as zf:
                namelist = zf.namelist()
                self.assertEqual(namelist[0], "mimetype")
                self.assertEqual(zf.infolist()[0].compress_type, zipfile.ZIP_STORED)
                self.assertIn("META-INF/container.xml", namelist)

                opf_rel = find_opf_path(extracted_dir)
                self.assertIn(opf_rel, namelist)

                xhtml_files = list_xhtml_files(extracted_dir, opf_path)
                opf_base = Path(opf_rel).parent
                for href in xhtml_files:
                    full_href = str(opf_base / href) if str(opf_base) != "." else href
                    self.assertIn(full_href, namelist,
                                  f"Falta {full_href} en EPUB reconstruido")

                for href in xhtml_files:
                    full_href = str(opf_base / href) if str(opf_base) != "." else href
                    data = zf.read(full_href)
                    etree.fromstring(data)

            re_extracted = tmp_path / "re_extracted"
            with zipfile.ZipFile(rebuilt_epub, "r") as zf:
                zf.extractall(re_extracted)
            self.assertTrue((re_extracted / "mimetype").exists())

    def test_roundtrip(self) -> None:
        for epub_path in _epub_files():
            with self.subTest(epub=epub_path.name):
                self._roundtrip_epub(epub_path)


class PackageTestCase(unittest.TestCase):
    """Prueba el empaquetado directo de un EPUB extraído."""

    def test_package_epub_idempotent(self) -> None:
        epub_files = _epub_files()
        self.assertTrue(epub_files)
        epub_path = epub_files[0]

        with tempfile.TemporaryDirectory(prefix="epub_package_") as tmp:
            tmp_path = Path(tmp)
            extracted = tmp_path / "extracted"
            output = tmp_path / "out.epub"

            with zipfile.ZipFile(epub_path, "r") as zf:
                zf.extractall(extracted)

            package_epub(extracted, output)

            with zipfile.ZipFile(output, "r") as zf:
                self.assertEqual(zf.namelist()[0], "mimetype")
                self.assertEqual(zf.infolist()[0].compress_type, zipfile.ZIP_STORED)


if __name__ == "__main__":
    unittest.main()
