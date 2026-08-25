"""Reconstruye un EPUB a partir de un directorio extraído y unidades traducidas."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lxml import etree

from .models import ExtractedDocument, Placeholder, TranslationUnit
from .utils import (
    XHTML_NS,
    opf_dir,
    package_epub,
    parse_xhtml,
    serialize_xhtml,
    split_text_with_placeholders,
)
from .extractor import TMP_ID_ATTR_NO_NS


def _append_text(current: etree._Element, text: str) -> None:
    """Añade texto al lugar correcto: text del nodo o tail del último hijo."""
    if not text:
        return
    if len(current) == 0:
        if current.text is None:
            current.text = text
        else:
            current.text += text
    else:
        last = current[-1]
        if last.tail is None:
            last.tail = text
        else:
            last.tail += text


def _apply_translated_attrs(element: etree._Element, key: str,
                            translated_attrs: dict[str, dict[str, str]] | None) -> None:
    """Aplica atributos traducidos a un elemento si existen."""
    if not translated_attrs:
        return
    attrs = translated_attrs.get(key)
    if not attrs:
        return
    for attr_name, attr_value in attrs.items():
        element.set(attr_name, attr_value)


def _build_element(text: str, placeholders: dict[str, Placeholder],
                   block_tag: str,
                   translated_attrs: dict[str, dict[str, str]] | None = None) -> etree._Element:
    """Construye un árbol DOM a partir de texto con placeholders."""
    root = etree.Element(f"{{{XHTML_NS}}}{block_tag}")
    stack: list[tuple[etree._Element, str | None]] = [(root, None)]

    for segment, ph_id in split_text_with_placeholders(text):
        if ph_id is None:
            current, _ = stack[-1]
            _append_text(current, segment)
        else:
            ph = placeholders[ph_id]
            current, _ = stack[-1]
            if ph.self_closing:
                el = etree.Element(f"{{{XHTML_NS}}}{ph.tag}", ph.attrs)
                _apply_translated_attrs(el, ph_id, translated_attrs)
                current.append(el)
            else:
                # Si el tope de la pila fue abierto por este mismo placeholder,
                # es un cierre; si no, es una apertura.
                if stack[-1][1] == ph_id:
                    stack.pop()
                else:
                    el = etree.Element(f"{{{XHTML_NS}}}{ph.tag}", ph.attrs)
                    _apply_translated_attrs(el, ph_id, translated_attrs)
                    current.append(el)
                    stack.append((el, ph_id))

    _apply_translated_attrs(root, "self", translated_attrs)
    return root


def _apply_unit(element: etree._Element, unit: TranslationUnit) -> None:
    """Reemplaza el contenido de un elemento block por su texto traducido."""
    if unit.translation is None:
        # Sin traducción se conserva el elemento original intacto.
        return

    text = unit.translation
    if not text.strip():
        return

    block_tag = element.tag.split("}")[-1] if element.tag.startswith("{") else element.tag
    new_root = _build_element(text, unit.placeholders, block_tag, unit.translated_attrs)

    # Limpiar contenido anterior.
    for child in list(element):
        element.remove(child)
    element.text = new_root.text
    for child in list(new_root):
        element.append(child)


def _remove_tmp_ids(root: etree._Element) -> None:
    """Elimina los atributos temporales dejados por el extractor."""
    for element in root.iter():
        if TMP_ID_ATTR_NO_NS in element.attrib:
            del element.attrib[TMP_ID_ATTR_NO_NS]


class Reconstructor:
    """Reconstruye un EPUB a partir de un directorio extraído."""

    def __init__(self, extracted_dir: str | Path,
                 translation_units_path: str | Path) -> None:
        self.extracted_dir = Path(extracted_dir)
        with open(translation_units_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.document = ExtractedDocument.from_dict(data)

    def reconstruct(self, output_epub: str | Path,
                    update_language: str | None = None) -> Path:
        """Genera el EPUB reconstruido."""
        output_epub = Path(output_epub)
        work_dir = self.extracted_dir.with_suffix(".rebuild")
        if work_dir.exists():
            shutil.rmtree(work_dir)
        shutil.copytree(self.extracted_dir, work_dir)

        opf_path = self.document.source_epub  # no usado aquí directamente
        from .utils import find_opf_path
        opf_rel = find_opf_path(work_dir)
        base_dir = work_dir / opf_dir(opf_rel)

        for href, extracted_file in self.document.files.items():
            xhtml_path = base_dir / href
            if not xhtml_path.exists():
                continue

            tree = parse_xhtml(xhtml_path)
            root = tree.getroot()
            id_map = {
                el.get(TMP_ID_ATTR_NO_NS): el
                for el in root.iter()
                if TMP_ID_ATTR_NO_NS in el.attrib
            }

            for unit in extracted_file.units:
                element = id_map.get(unit.unit_id)
                if element is None:
                    continue
                _apply_unit(element, unit)

            _remove_tmp_ids(root)
            serialize_xhtml(tree, xhtml_path)

        if update_language:
            self._update_language(work_dir, opf_rel, update_language)

        package_epub(work_dir, output_epub)
        shutil.rmtree(work_dir)
        return output_epub

    def _update_language(self, work_dir: Path, opf_rel: str, language: str) -> None:
        """Actualiza <dc:language> en el .opf cuando se traduce."""
        opf_path = work_dir / opf_rel
        if not opf_path.exists():
            return

        tree = parse_xhtml(opf_path)
        root = tree.getroot()
        ns = {"opf": "http://www.idpf.org/2007/opf",
              "dc": "http://purl.org/dc/elements/1.1/"}
        lang_nodes = root.xpath("//dc:language", namespaces=ns)
        if lang_nodes:
            lang_nodes[0].text = language
        else:
            metadata = root.xpath("//opf:metadata", namespaces=ns)
            if metadata:
                el = etree.Element(f"{{{ns['dc']}}}language")
                el.text = language
                metadata[0].append(el)
        serialize_xhtml(tree, opf_path)
