"""Tests para el módulo de traducción."""

from __future__ import annotations

import unittest

from epub_toolkit.models import ExtractedDocument, ExtractedFile, TranslationUnit
from epub_toolkit.translator import (
    DummyTranslator,
    OllamaTranslator,
    OpenAITranslator,
    _batch_prompt,
    _format_glossary,
    _parse_numbered_translations,
    _protect_glossary,
    _restore_glossary,
    _system_prompt,
    create_translator,
    translate_batch_for_file,
    translate_document,
    translate_unit,
)


class PlaceholderProtectionTestCase(unittest.TestCase):
    """Verifica que los placeholders se protegen y restauran correctamente."""

    def test_translate_unit_preserves_placeholders(self) -> None:
        unit = TranslationUnit(
            unit_id="u1",
            xpath="//p[1]",
            original="Hello {ph0}world{ph0}.",
            placeholders={"{ph0}": {"tag": "b", "attrs": {}, "self_closing": False}},
        )
        translator = DummyTranslator(expansion=1.0)
        result = translate_unit(translator, unit, "en", "es")
        self.assertIn("{ph0}", result)
        self.assertIn("world", result)
        self.assertTrue(result.startswith("[ES]") and result.endswith("[ES]"))

    def test_self_closing_placeholder(self) -> None:
        unit = TranslationUnit(
            unit_id="u2",
            xpath="//p[2]",
            original="Line one{ph0}line two",
            placeholders={"{ph0}": {"tag": "br", "attrs": {}, "self_closing": True}},
        )
        translator = DummyTranslator(expansion=1.0)
        result = translate_unit(translator, unit, "en", "es")
        self.assertIn("{ph0}", result)


class DummyTranslatorTestCase(unittest.TestCase):
    """Pruebas del traductor de prueba."""

    def test_expansion(self) -> None:
        translator = DummyTranslator(expansion=2.0)
        text = "hello"
        result = translator.translate(text, "en", "es")
        self.assertEqual(result, "[ES] hello hello [ES]")

    def test_no_expansion(self) -> None:
        translator = DummyTranslator(expansion=1.0)
        result = translator.translate("hello", "en", "es")
        self.assertEqual(result, "[ES] hello [ES]")


class TranslateDocumentTestCase(unittest.TestCase):
    """Pruebas de traducción a nivel de documento."""

    def test_translate_document(self) -> None:
        unit = TranslationUnit(
            unit_id="u1",
            xpath="//p[1]",
            original="Hello world.",
            placeholders={},
        )
        document = ExtractedDocument(
            source_epub="test.epub",
            language="en",
            files={"xhtml/ch1.xhtml": ExtractedFile(path="xhtml/ch1.xhtml", units=[unit])},
        )
        translator = DummyTranslator(expansion=1.0)
        translate_document(translator, document, progress=False)
        self.assertIsNotNone(unit.translation)
        self.assertIn("[ES]", unit.translation)


class FactoryTestCase(unittest.TestCase):
    """Pruebas de la factoría de traductores."""

    def test_create_dummy(self) -> None:
        t = create_translator("dummy", expansion=1.5)
        self.assertIsInstance(t, DummyTranslator)

    def test_create_unknown(self) -> None:
        with self.assertRaises(ValueError):
            create_translator("unknown")

    def test_create_openai(self) -> None:
        t = create_translator("openai", api_key="test", model="gpt-4o")
        self.assertIsInstance(t, OpenAITranslator)

    def test_create_ollama(self) -> None:
        t = create_translator("ollama", model="llama3.2")
        self.assertIsInstance(t, OllamaTranslator)


class PromptTestCase(unittest.TestCase):
    """Verifica que el prompt de sistema preserve placeholders."""

    def test_prompt_preserves_placeholders(self) -> None:
        prompt = _system_prompt("en", "es", expansion_hint=1.25)
        self.assertIn("{ph0}", prompt)
        self.assertIn("NO traduzcas", prompt)
        self.assertIn("25%", prompt)

    def test_batch_prompt_includes_context(self) -> None:
        prompt = _batch_prompt(["Hello", "World"], "en", "es",
                               context_title="Chapter 1", expansion_hint=1.25)
        self.assertIn("Chapter 1", prompt)
        self.assertIn("1. Hello", prompt)
        self.assertIn("2. World", prompt)


class ParseNumberedTranslationsTestCase(unittest.TestCase):
    """Prueba el parseo de respuestas numeradas de LLMs."""

    def test_parse_numbered_list(self) -> None:
        response = "1. Hola mundo\n2. Adiós mundo"
        result = _parse_numbered_translations(response, 2)
        self.assertEqual(result, ["Hola mundo", "Adiós mundo"])

    def test_parse_fallback_lines(self) -> None:
        response = "Hola mundo\nAdiós mundo"
        result = _parse_numbered_translations(response, 2)
        self.assertEqual(result, ["Hola mundo", "Adiós mundo"])

    def test_parse_failure(self) -> None:
        response = "Hola mundo"
        result = _parse_numbered_translations(response, 2)
        self.assertEqual(result, [])


class BatchTranslationTestCase(unittest.TestCase):
    """Prueba la traducción por lotes por archivo."""

    def test_translate_batch_for_file(self) -> None:
        unit1 = TranslationUnit(
            unit_id="u1", xpath="//p[1]",
            original="Hello world.", placeholders={},
        )
        unit2 = TranslationUnit(
            unit_id="u2", xpath="//p[2]",
            original="Goodbye world.", placeholders={},
        )
        file = ExtractedFile(path="xhtml/ch1.xhtml", units=[unit1, unit2],
                             context_title="Chapter 1")
        translator = DummyTranslator(expansion=1.0)
        translations = translate_batch_for_file(translator, file, "en", "es")
        self.assertEqual(len(translations), 2)
        self.assertTrue(all("[ES]" in t for t in translations))

    def test_translate_document_batches(self) -> None:
        unit = TranslationUnit(
            unit_id="u1", xpath="//p[1]",
            original="Hello world.", placeholders={},
        )
        document = ExtractedDocument(
            source_epub="test.epub",
            language="en",
            files={"xhtml/ch1.xhtml": ExtractedFile(path="xhtml/ch1.xhtml",
                                                    units=[unit],
                                                    context_title="Chapter 1")},
        )
        translator = DummyTranslator(expansion=1.0)
        translate_document(translator, document, progress=False)
        self.assertIsNotNone(unit.translation)
        self.assertIn("[ES]", unit.translation)


class GlossaryTestCase(unittest.TestCase):
    """Pruebas del glosario de términos técnicos."""

    def test_protect_and_restore_glossary(self) -> None:
        glossary = {"large language model": "gran modelo de lenguaje"}
        text = "A large language model is useful."
        protected, mapping = _protect_glossary(text, glossary)
        self.assertIn("___GLS0___", protected)
        restored = _restore_glossary(protected, mapping)
        self.assertEqual(restored, "A gran modelo de lenguaje is useful.")

    def test_glossary_with_placeholders(self) -> None:
        glossary = {"large language model": "gran modelo de lenguaje"}
        unit = TranslationUnit(
            unit_id="u1", xpath="//p[1]",
            original="A {ph0}large language model{ph0} is useful.",
            placeholders={"{ph0}": {"tag": "b", "attrs": {}, "self_closing": False}},
        )
        file = ExtractedFile(path="xhtml/ch1.xhtml", units=[unit],
                             context_title="Chapter 1")
        translator = DummyTranslator(expansion=1.0)
        result = translate_batch_for_file(translator, file, "en", "es",
                                          glossary=glossary)[0]
        self.assertIn("{ph0}", result)
        self.assertIn("gran modelo de lenguaje", result)
        self.assertNotIn("large language model", result)

    def test_format_glossary(self) -> None:
        text = _format_glossary({"prompt": "instrucción"})
        self.assertIn("prompt -> instrucción", text)

    def test_system_prompt_with_glossary(self) -> None:
        prompt = _system_prompt("en", "es", glossary={"prompt": "instrucción"})
        self.assertIn("prompt -> instrucción", prompt)
        self.assertIn("___GLS0___", prompt)


if __name__ == "__main__":
    unittest.main()
