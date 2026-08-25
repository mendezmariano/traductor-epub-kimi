"""Utilidades compartidas para manipular EPUBs y XML."""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import Iterable

from lxml import etree


# Tags inline que se preservan dentro de una unidad de traducción.
INLINE_TAGS: set[str] = {
    "a",
    "abbr",
    "b",
    "bdi",
    "bdo",
    "big",
    "br",
    "cite",
    "code",
    "data",
    "dfn",
    "em",
    "i",
    "img",
    "input",
    "kbd",
    "mark",
    "q",
    "rp",
    "rt",
    "ruby",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "time",
    "var",
    "wbr",
}

# Tags de bloque que definen una unidad de traducción cuando contienen texto.
BLOCK_TAGS: set[str] = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "td",
    "th",
    "caption",
    "figcaption",
    "blockquote",
    "aside",
    "dt",
    "dd",
    "summary",
    "label",
}

# Tags cuyo contenido no se traduce (se ignoran completamente).
SKIPPED_TAGS: set[str] = {
    "script",
    "style",
    "pre",
    "svg",
    "math",
    "head",
    "link",
    "meta",
    "title",
    "nav",  # Los nav EPUB suelen ser índices; se tratan aparte si es necesario.
}

# Atributos que pueden contener texto traducible.
TRANSLATABLE_ATTRS: set[str] = {"alt", "title", "aria-label", "placeholder"}

# Tags vacíos (self-closing) en HTML/XHTML.
VOID_TAGS: set[str] = {"area", "base", "br", "col", "embed", "hr", "img",
                       "input", "link", "meta", "param", "source", "track", "wbr"}

# Namespace XHTML por defecto.
XHTML_NS = "http://www.w3.org/1999/xhtml"
NSMAP = {"html": XHTML_NS}


def find_opf_path(extracted_dir: str | Path) -> str:
    """Lee META-INF/container.xml y devuelve la ruta relativa del .opf."""
    container_path = Path(extracted_dir) / "META-INF" / "container.xml"
    if not container_path.exists():
        raise FileNotFoundError(f"No se encontró {container_path}")

    tree = etree.parse(str(container_path))
    rootfile = tree.xpath("//n:rootfile[@media-type='application/oebps-package+xml']",
                          namespaces={"n": "urn:oasis:names:tc:opendocument:xmlns:container"})
    if not rootfile:
        rootfile = tree.xpath("//rootfile[@media-type='application/oebps-package+xml']")
    if not rootfile:
        raise ValueError("No se encontró rootfile válido en container.xml")

    return rootfile[0].get("full-path")


def list_xhtml_files(extracted_dir: str | Path, opf_path: str | None = None) -> list[str]:
    """Devuelve las rutas relativas de los XHTML listados en el manifest del .opf."""
    extracted_dir = Path(extracted_dir)
    if opf_path is None:
        opf_path = find_opf_path(extracted_dir)

    opf_full = extracted_dir / opf_path
    tree = etree.parse(str(opf_full))
    items = tree.xpath("//opf:item[@media-type='application/xhtml+xml']",
                       namespaces={"opf": "http://www.idpf.org/2007/opf"})
    if not items:
        items = tree.xpath("//item[@media-type='application/xhtml+xml']")

    return sorted({item.get("href") for item in items if item.get("href")})


def opf_dir(opf_path: str) -> str:
    """Directorio base relativo del .opf (p.ej. 'OEBPS')."""
    return os.path.dirname(opf_path) or "."


def parse_xhtml(path: str | Path) -> etree._ElementTree:
    """Parsea un XHTML respetando namespaces; usa html como fallback."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    try:
        return etree.parse(str(path), parser)
    except etree.XMLSyntaxError:
        from lxml import html
        return html.parse(str(path))


def _has_xml_declaration(path: Path) -> bool:
    """Comprueba si un archivo empieza con declaración XML."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
        return head.startswith(b"<?xml")
    except FileNotFoundError:
        return False


def _ensure_non_void_closed(root: etree._Element) -> None:
    """Fuerza etiquetas de cierre para elementos no vacíos que quedaron vacíos."""
    for element in root.iter():
        tag = element.tag
        if not isinstance(tag, str):
            continue
        local = tag.split("}")[-1] if tag.startswith("{") else tag
        if local not in VOID_TAGS and element.text is None and len(element) == 0:
            element.text = ""


def _detect_eol(path: Path) -> str:
    """Detecta el tipo de fin de línea predominante del archivo original."""
    try:
        with open(path, "rb") as f:
            sample = f.read(8192)
    except FileNotFoundError:
        return "\n"
    crlf = sample.count(b"\r\n")
    lf = sample.count(b"\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def _normalize_xml_quotes(text: str) -> str:
    """lxml emite <?xml version='1.0' encoding='UTF-8'?>; normalizamos a dobles."""
    if text.startswith("<?xml"):
        end = text.find("?>")
        if end != -1:
            decl = text[:end + 2]
            decl = decl.replace("version='", 'version="').replace("' encoding=", '" encoding=')
            decl = decl.replace("encoding='", 'encoding="').replace("'?>", '"?>')
            text = decl + text[end + 2:]
    return text


def serialize_xhtml(tree: etree._ElementTree, path: str | Path,
                    xml_declaration: bool | None = None) -> None:
    """Serializa un árbol XHTML respetando el estilo del archivo original.

    Si xml_declaration es None, se infiere a partir del archivo existente.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_non_void_closed(tree.getroot())

    if xml_declaration is None:
        xml_declaration = _has_xml_declaration(path)

    eol = _detect_eol(path)

    # Guardamos si el archivo original terminaba con newline antes de sobreescribir.
    had_trailing_newline = False
    try:
        with open(path, "rb") as f:
            original_bytes = f.read()
        if original_bytes.endswith(b"\r\n") or original_bytes.endswith(b"\n"):
            had_trailing_newline = True
    except FileNotFoundError:
        pass

    tree.write(
        str(path),
        encoding="utf-8",
        xml_declaration=xml_declaration,
        doctype='<!DOCTYPE html>' if xml_declaration else None,
        method="xml",
        pretty_print=False,
    )

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = _normalize_xml_quotes(text)
    if eol == "\r\n":
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    if had_trailing_newline and not text.endswith(eol):
        text += eol
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def package_epub(source_dir: str | Path, output_epub: str | Path) -> None:
    """Empaqueta un directorio extraído en un EPUB/ZIP válido.

    El archivo mimetype debe ir primero y sin compresión.
    """
    source_dir = Path(source_dir)
    output_epub = Path(output_epub)
    output_epub.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_epub, "w", zipfile.ZIP_DEFLATED) as zf:
        mimetype_path = source_dir / "mimetype"
        if mimetype_path.exists():
            zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

        for file_path in _walk_files(source_dir):
            arcname = str(file_path.relative_to(source_dir))
            if arcname == "mimetype":
                continue
            zf.write(file_path, arcname)


def _walk_files(root: Path) -> Iterable[Path]:
    """Recorre todos los archivos de un directorio de forma determinista."""
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def make_placeholder(index: int) -> str:
    """Genera un token placeholder único."""
    return f"{{ph{index}}}"


_PLACEHOLDER_RE = re.compile(r"\{ph(\d+)\}")


def iter_placeholders(text: str) -> Iterable[tuple[int, int, int]]:
    """Itera sobre los placeholders en un texto (start, end, index)."""
    for m in _PLACEHOLDER_RE.finditer(text):
        yield m.start(), m.end(), int(m.group(1))


def split_text_with_placeholders(text: str) -> list[tuple[str, str | None]]:
    """Divide un texto en segmentos de texto plano y placeholders.

    Devuelve una lista de (texto, placeholder_id | None).
    """
    result: list[tuple[str, str | None]] = []
    cursor = 0
    for start, end, idx in iter_placeholders(text):
        if start > cursor:
            result.append((text[cursor:start], None))
        result.append((text[start:end], make_placeholder(idx)))
        cursor = end
    if cursor < len(text):
        result.append((text[cursor:], None))
    return result


def clean_text(text: str | None) -> str:
    """Normaliza espacios en blanco de un texto extraído."""
    if text is None:
        return ""
    # Preservamos espacios iniciales/finales si el texto original los tenía,
    # pero normalizamos secuencias de espacios múltiples.
    return re.sub(r"[ \t]+", " ", text).replace("\n", " ")


def has_translatable_text(element: etree._Element) -> bool:
    """Determina si un elemento contiene texto visible traducible."""
    if element.tag in SKIPPED_TAGS:
        return False
    text = "".join(element.itertext())
    return bool(text and text.strip())
