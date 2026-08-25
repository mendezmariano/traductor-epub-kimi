"""Analizador estructural de EPUBs.

Proporciona funciones para inspeccionar la estructura completa de un EPUB:
archivos, DOM de cada XHTML y hojas de estilo CSS.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from .utils import find_opf_path, list_xhtml_files, parse_xhtml


def _local_name(element: etree._Element) -> str:
    """Devuelve el nombre local de un tag sin namespace."""
    tag = element.tag
    if isinstance(tag, str):
        return tag.split("}")[-1] if tag.startswith("{") else tag
    return ""


def _count_dom(root: etree._Element) -> dict[str, int]:
    """Cuenta elementos, atributos y nodos de texto de un árbol."""
    elements = 0
    attributes = 0
    text_nodes = 0

    for element in root.iter():
        elements += 1
        attributes += len(element.attrib)
        if element.text and element.text.strip():
            text_nodes += 1
        if element.tail and element.tail.strip():
            text_nodes += 1

    return {
        "elements": elements,
        "attributes": attributes,
        "text_nodes": text_nodes,
    }


def _inline_styles(root: etree._Element) -> list[str]:
    """Recoge los valores de atributos style encontrados en el XHTML."""
    styles: list[str] = []
    for element in root.iter():
        style = element.attrib.get("style")
        if style:
            styles.append(style)
    return styles


def _file_hash(path: Path) -> str:
    """Calcula SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def analyze_xhtml(path: Path) -> dict[str, Any]:
    """Analiza un archivo XHTML y devuelve métricas estructurales."""
    tree = parse_xhtml(path)
    root = tree.getroot()
    counts = _count_dom(root)
    return {
        "path": str(path),
        "local_name": _local_name(root),
        **counts,
        "inline_styles": _inline_styles(root),
        "inline_style_count": len(_inline_styles(root)),
    }


def analyze_css(path: Path) -> dict[str, Any]:
    """Analiza una hoja de estilo CSS."""
    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _file_hash(path),
        "line_count": content.count("\n") + 1,
    }


def analyze_binary(path: Path) -> dict[str, Any]:
    """Analiza un archivo binario (imagen, fuente, etc.)."""
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _file_hash(path),
    }


def analyze_epub(epub_path: str | Path) -> dict[str, Any]:
    """Analiza un EPUB y devuelve un resumen estructural completo.

    El análisis se realiza sobre una extracción temporal del ZIP.
    """
    epub_path = Path(epub_path)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="epub_analyze_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(epub_path, "r") as zf:
            zf.extractall(tmp_path)

        opf_path = find_opf_path(tmp_path)
        xhtml_files = list_xhtml_files(tmp_path, opf_path)

        files: list[dict[str, Any]] = []
        xhtml_analysis: list[dict[str, Any]] = []
        css_analysis: list[dict[str, Any]] = []
        binary_analysis: list[dict[str, Any]] = []

        for file_path in sorted(tmp_path.rglob("*")):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(tmp_path)
            rel_str = str(rel_path).replace("\\", "/")

            if rel_str in ("mimetype",):
                files.append({"path": rel_str, "type": "mimetype", "size": file_path.stat().st_size})
                continue

            if rel_str.endswith(".xhtml") or rel_str.endswith(".html"):
                info = analyze_xhtml(file_path)
                info["rel_path"] = rel_str
                xhtml_analysis.append(info)
                files.append({"path": rel_str, "type": "xhtml", "size": file_path.stat().st_size})
            elif rel_str.endswith(".css"):
                info = analyze_css(file_path)
                info["rel_path"] = rel_str
                css_analysis.append(info)
                files.append({"path": rel_str, "type": "css", "size": file_path.stat().st_size})
            else:
                info = analyze_binary(file_path)
                info["rel_path"] = rel_str
                binary_analysis.append(info)
                files.append({"path": rel_str, "type": "binary", "size": file_path.stat().st_size})

        return {
            "epub_path": str(epub_path),
            "opf_path": opf_path,
            "xhtml_files": xhtml_files,
            "files": files,
            "xhtml": xhtml_analysis,
            "css": css_analysis,
            "binary": binary_analysis,
            "total_files": len(files),
            "total_xhtml": len(xhtml_analysis),
            "total_css": len(css_analysis),
            "total_binary": len(binary_analysis),
        }


def compare_epubs(original_path: str | Path, rebuilt_path: str | Path) -> dict[str, Any]:
    """Compara dos EPUBs y devuelve un reporte de diferencias estructurales."""
    original = analyze_epub(original_path)
    rebuilt = analyze_epub(rebuilt_path)

    differences: list[dict[str, Any]] = []

    # Comparar conjuntos de archivos.
    original_files = {f["path"] for f in original["files"]}
    rebuilt_files = {f["path"] for f in rebuilt["files"]}

    missing_in_rebuilt = original_files - rebuilt_files
    extra_in_rebuilt = rebuilt_files - original_files

    if missing_in_rebuilt:
        differences.append({"type": "missing_files", "paths": sorted(missing_in_rebuilt)})
    if extra_in_rebuilt:
        differences.append({"type": "extra_files", "paths": sorted(extra_in_rebuilt)})

    # Comparar XHTML estructuralmente.
    original_xhtml = {x["rel_path"]: x for x in original["xhtml"]}
    rebuilt_xhtml = {x["rel_path"]: x for x in rebuilt["xhtml"]}

    for path, orig in original_xhtml.items():
        reb = rebuilt_xhtml.get(path)
        if reb is None:
            continue
        for key in ("elements", "attributes", "text_nodes", "inline_style_count"):
            if orig[key] != reb[key]:
                differences.append({
                    "type": "xhtml_structural_diff",
                    "path": path,
                    "field": key,
                    "original": orig[key],
                    "rebuilt": reb[key],
                })

    # Comparar CSS por contenido (hash).
    original_css = {c["rel_path"]: c["sha256"] for c in original["css"]}
    rebuilt_css = {c["rel_path"]: c["sha256"] for c in rebuilt["css"]}

    for path, orig_hash in original_css.items():
        reb_hash = rebuilt_css.get(path)
        if reb_hash is not None and orig_hash != reb_hash:
            differences.append({
                "type": "css_content_diff",
                "path": path,
                "original_sha256": orig_hash,
                "rebuilt_sha256": reb_hash,
            })

    # Comparar archivos binarios por hash.
    original_bin = {b["rel_path"]: b["sha256"] for b in original["binary"]}
    rebuilt_bin = {b["rel_path"]: b["sha256"] for b in rebuilt["binary"]}

    for path, orig_hash in original_bin.items():
        reb_hash = rebuilt_bin.get(path)
        if reb_hash is not None and orig_hash != reb_hash:
            differences.append({
                "type": "binary_hash_diff",
                "path": path,
                "original_sha256": orig_hash,
                "rebuilt_sha256": reb_hash,
            })

    return {
        "original": original["epub_path"],
        "rebuilt": rebuilt["epub_path"],
        "differences": differences,
        "difference_count": len(differences),
        "equivalent": len(differences) == 0,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 -m epub_toolkit.analyzer <ruta-al-epub>")
        sys.exit(1)
    result = analyze_epub(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
