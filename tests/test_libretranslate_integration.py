"""Test de integración de LibreTranslate con un servidor mock."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.models import ExtractedDocument, ExtractedFile, TranslationUnit
from epub_toolkit.translator import (
    LibreTranslateTranslator,
    translate_batch_for_file,
    translate_document,
    translate_unit,
)


class MockLibreTranslateHandler(BaseHTTPRequestHandler):
    """Servidor mock que simula /translate de LibreTranslate."""

    # Variables de clase configurables por los tests.
    response_type: str = "ok"
    received_api_key: str | None = None
    received_texts: list[str] | str | None = None

    def do_POST(self) -> None:
        self.received_api_key = None
        self.received_texts = None

        if self.path != "/translate":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            texts = data.get("q", "")
            target = data.get("target", "es")
            MockLibreTranslateHandler.received_texts = texts
            MockLibreTranslateHandler.received_api_key = data.get("api_key")
            marker = f"[{target.upper()}]"

            if self.response_type == "404":
                self.send_response(404)
                self.end_headers()
                return
            if self.response_type == "500":
                self.send_response(500)
                self.end_headers()
                return
            if self.response_type == "missing_field":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({}).encode("utf-8"))
                return
            if self.response_type == "wrong_count":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {"translatedText": [f"{marker} {texts[0]} {marker}"]}
                self.wfile.write(json.dumps(response).encode("utf-8"))
                return

            # Respuesta normal.
            if isinstance(texts, list):
                translated = [f"{marker} {t} {marker}" for t in texts]
            else:
                translated = f"{marker} {texts} {marker}"
            response = {"translatedText": translated}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        pass


class LibreTranslateIntegrationTestCase(unittest.TestCase):
    """Prueba el traductor de LibreTranslate contra un servidor local."""

    @classmethod
    def setUpClass(cls) -> None:
        MockLibreTranslateHandler.response_type = "ok"
        cls.server = HTTPServer(("127.0.0.1", 0), MockLibreTranslateHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    def tearDown(self) -> None:
        MockLibreTranslateHandler.response_type = "ok"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _translator(self, **kwargs) -> LibreTranslateTranslator:
        defaults = {"base_url": f"http://127.0.0.1:{self.port}", "delay": 0}
        defaults.update(kwargs)
        return LibreTranslateTranslator(**defaults)

    def test_translate_via_mock(self) -> None:
        translator = self._translator()
        result = translator.translate("Hello world", "en", "es")
        self.assertEqual(result, "[ES] Hello world [ES]")

    def test_translate_unit_preserves_placeholders(self) -> None:
        unit = TranslationUnit(
            unit_id="u1",
            xpath="//p[1]",
            original="Hello {ph0}world{ph0}.",
            placeholders={"{ph0}": {"tag": "b", "attrs": {}, "self_closing": False}},
        )
        translator = self._translator()
        result = translate_unit(translator, unit, "en", "es")
        self.assertIn("{ph0}", result)
        self.assertIn("world", result)
        self.assertTrue(result.startswith("[ES]") and result.endswith("[ES]"))

    def test_translate_batch(self) -> None:
        translator = self._translator()
        results = translator.translate_batch(
            ["Hello world", "Goodbye world"], "en", "es"
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "[ES] Hello world [ES]")
        self.assertEqual(results[1], "[ES] Goodbye world [ES]")

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
        translator = self._translator()
        translations = translate_batch_for_file(translator, file, "en", "es")
        self.assertEqual(len(translations), 2)
        self.assertTrue(all("[ES]" in t for t in translations))

    def test_translate_document(self) -> None:
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
        translator = self._translator()
        translate_document(translator, document, progress=False)
        self.assertIsNotNone(unit.translation)
        self.assertIn("[ES]", unit.translation)

    def test_api_key_is_sent(self) -> None:
        translator = self._translator(api_key="secret-key")
        result = translator.translate("Hello", "en", "es")
        self.assertEqual(result, "[ES] Hello [ES]")
        self.assertEqual(MockLibreTranslateHandler.received_api_key, "secret-key")

    def test_delay_is_accepted(self) -> None:
        import time
        translator = self._translator(delay=0.05)
        start = time.monotonic()
        result = translator.translate("Hello", "en", "es")
        elapsed = time.monotonic() - start
        self.assertIn("[ES]", result)
        self.assertGreaterEqual(elapsed, 0.05)

    def test_error_404(self) -> None:
        MockLibreTranslateHandler.response_type = "404"
        translator = self._translator()
        with self.assertRaises(RuntimeError):
            translator.translate("Hello", "en", "es")

    def test_error_500(self) -> None:
        MockLibreTranslateHandler.response_type = "500"
        translator = self._translator()
        with self.assertRaises(RuntimeError):
            translator.translate("Hello", "en", "es")

    def test_missing_translated_text(self) -> None:
        MockLibreTranslateHandler.response_type = "missing_field"
        translator = self._translator()
        with self.assertRaises(RuntimeError) as cm:
            translator.translate("Hello", "en", "es")
        self.assertIn("translatedText", str(cm.exception))

    def test_wrong_text_count(self) -> None:
        MockLibreTranslateHandler.response_type = "wrong_count"
        translator = self._translator()
        with self.assertRaises(RuntimeError) as cm:
            translator.translate_batch(["Hello", "World"], "en", "es")
        self.assertIn("devolvió 1 textos", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
