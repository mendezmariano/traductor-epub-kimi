"""Descompone un EPUB en un directorio de trabajo."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from .utils import find_opf_path


class Deconstructor:
    """Extrae el contenido de un EPUB manteniendo la estructura de rutas."""

    def __init__(self, epub_path: str | Path, output_dir: str | Path,
                 clean: bool = True) -> None:
        self.epub_path = Path(epub_path)
        self.output_dir = Path(output_dir)
        self.clean = clean

    def deconstruct(self) -> tuple[Path, str]:
        """Extrae el EPUB y devuelve (directorio_extraído, ruta_relativa_opf)."""
        if self.clean and self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(self.epub_path, "r") as zf:
            zf.extractall(self.output_dir)

        opf_path = find_opf_path(self.output_dir)
        return self.output_dir, opf_path
