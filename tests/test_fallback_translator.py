"""Tests para FallbackTranslator."""

from __future__ import annotations

import unittest
from typing import Any

from epub_toolkit.translator import (
    FallbackTranslator,
    QuotaExceededError,
    Translator,
)


class FailingTranslator(Translator):
    """Traductor que siempre falla."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        raise self.error

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: dict[str, str] | None = None,
                        **kwargs: Any) -> list[str]:
        raise self.error


class EchoTranslator(Translator):
    """Traductor que devuelve el texto marcado."""

    def __init__(self, prefix: str = "[ES]") -> None:
        self.prefix = prefix

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        return f"{self.prefix} {text}"

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str,
                        context_title: str = "",
                        glossary: dict[str, str] | None = None,
                        **kwargs: Any) -> list[str]:
        return [f"{self.prefix} {t}" for t in texts]


class FallbackTranslatorTestCase(unittest.TestCase):
    """Pruebas del traductor compuesto con fallback."""

    def test_first_translator_works(self) -> None:
        fb = FallbackTranslator([EchoTranslator("[A]"), EchoTranslator("[B]")])
        result = fb.translate("hello", "en", "es")
        self.assertEqual(result, "[A] hello")

    def test_fallback_on_quota_error(self) -> None:
        fb = FallbackTranslator([
            FailingTranslator(QuotaExceededError("quota")),
            EchoTranslator("[B]"),
        ])
        result = fb.translate("hello", "en", "es")
        self.assertEqual(result, "[B] hello")

    def test_fallback_on_runtime_error(self) -> None:
        fb = FallbackTranslator([
            FailingTranslator(RuntimeError("fallo")),
            EchoTranslator("[B]"),
        ])
        result = fb.translate("hello", "en", "es")
        self.assertEqual(result, "[B] hello")

    def test_all_fail(self) -> None:
        fb = FallbackTranslator([
            FailingTranslator(QuotaExceededError("quota 1")),
            FailingTranslator(RuntimeError("fallo 2")),
        ])
        with self.assertRaises(RuntimeError) as cm:
            fb.translate("hello", "en", "es")
        self.assertIn("Todos los traductores de fallback fallaron", str(cm.exception))

    def test_empty_translators_raises(self) -> None:
        with self.assertRaises(ValueError):
            FallbackTranslator([])

    def test_batch_fallback(self) -> None:
        fb = FallbackTranslator([
            FailingTranslator(QuotaExceededError("quota")),
            EchoTranslator("[B]"),
        ])
        results = fb.translate_batch(["hello", "world"], "en", "es")
        self.assertEqual(results, ["[B] hello", "[B] world"])


if __name__ == "__main__":
    unittest.main()
