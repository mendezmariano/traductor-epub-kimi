"""Modelos de datos para el traductor de EPUB."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Placeholder:
    """Representa un tag inline preservado dentro de una unidad de traducción."""

    tag: str
    attrs: dict[str, str]
    self_closing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "attrs": self.attrs,
            "self_closing": self.self_closing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Placeholder:
        return cls(
            tag=data["tag"],
            attrs=data.get("attrs", {}),
            self_closing=data.get("self_closing", False),
        )


@dataclass
class TranslationUnit:
    """Unidad de texto traducible extraída de un XHTML."""

    unit_id: str
    xpath: str
    original: str
    placeholders: dict[str, Placeholder] = field(default_factory=dict)
    translatable: bool = True
    translation: str | None = None
    translatable_attrs: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.unit_id,
            "xpath": self.xpath,
            "original": self.original,
            "placeholders": {
                key: ph.to_dict() for key, ph in self.placeholders.items()
            },
            "translatable": self.translatable,
            "translation": self.translation,
            "translatable_attrs": self.translatable_attrs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslationUnit:
        return cls(
            unit_id=data["id"],
            xpath=data["xpath"],
            original=data["original"],
            placeholders={
                key: Placeholder.from_dict(ph)
                for key, ph in data.get("placeholders", {}).items()
            },
            translatable=data.get("translatable", True),
            translation=data.get("translation"),
            translatable_attrs=data.get("translatable_attrs", {}),
        )


@dataclass
class ExtractedFile:
    """Unidades extraídas de un archivo XHTML concreto."""

    path: str
    units: list[TranslationUnit] = field(default_factory=list)
    context_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "context_title": self.context_title,
            "units": [unit.to_dict() for unit in self.units],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedFile:
        return cls(
            path=data["path"],
            units=[TranslationUnit.from_dict(u) for u in data.get("units", [])],
            context_title=data.get("context_title", ""),
        )


@dataclass
class ExtractedDocument:
    """Documento completo con todas las unidades extraídas de un EPUB."""

    source_epub: str
    language: str
    files: dict[str, ExtractedFile]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_epub": self.source_epub,
            "language": self.language,
            "files": {
                path: f.to_dict() for path, f in self.files.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedDocument:
        return cls(
            source_epub=data["source_epub"],
            language=data.get("language", "en"),
            files={
                path: ExtractedFile.from_dict(f)
                for path, f in data.get("files", {}).items()
            },
        )
