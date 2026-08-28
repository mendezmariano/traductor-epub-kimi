"""Tests de integración de DeepL con un servidor mock."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.models import ExtractedDocument, ExtractedFile, TranslationUnit
from epub_toolkit.translator import (
    DeepLTranslator,
    QuotaExceededError,
    translate_batch_for_file,
    translate_document,
    translate_unit,
)


class MockDeepLHandler(BaseHTTPRequestHandler):
    """Servidor mock que simula /v2/translate de DeepL."""

    response_type: str = "ok"
    received_auth: str | None = None
    received_texts: list[str] | None = None

    def do_POST(self) -> None:
        MockDeepLHandler.received_auth = None
        MockDeepLHandler.received_texts = None

        if self.path != "/v2/translate":
            self.send_response(404)
            self.end_headers()
            return

        auth = self.headers.get("Authorization", "")
        MockDeepLHandler.received_auth = auth

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            texts = data.get("text", [])
            target = data.get("target_lang", "ES")
            MockDeepLHandler.received_texts = texts

            if self.response_type == "quota":
                self.send_response(456)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"message": "Quota exceeded"}).encode("utf-8"))
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

            if isinstance(texts, list):
                translated = [{"text": f"[{target}] {t} [{target}]"} for t in texts]
            else:
                translated = [{"text": f"[{target}] {texts} [{target}]"}]
            response = {"translations": translated}
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


class DeepLIntegrationTestCase(unittest.TestCase):
    """Prueba el traductor de DeepL contra un servidor local."""

    @classmethod
    def setUpClass(cls) -> None:
        MockDeepLHandler.response_type = "ok"
        cls.server = HTTPServer(("127.0.0.1", 0), MockDeepLHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    def tearDown(self) -> None:
        MockDeepLHandler.response_type = "ok"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _translator(self, **kwargs) -> DeepLTranslator:
        defaults = {"base_url": f"http://127.0.0.1:{self.port}", "api_key": "test-key"}
        defaults.update(kwargs)
        return DeepLTranslator(**defaults)

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
        translator.translate("Hello", "en", "es")
        self.assertEqual(MockDeepLHandler.received_auth, "DeepL-Auth-Key secret-key")

    def test_quota_exceeded(self) -> None:
        MockDeepLHandler.response_type = "quota"
        translator = self._translator()
        with self.assertRaises(QuotaExceededError):
            translator.translate("Hello", "en", "es")

    def test_error_500(self) -> None:
        MockDeepLHandler.response_type = "500"
        translator = self._translator()
        with self.assertRaises(RuntimeError):
            translator.translate("Hello", "en", "es")

    def test_missing_translations(self) -> None:
        MockDeepLHandler.response_type = "missing_field"
        translator = self._translator()
        with self.assertRaises(RuntimeError) as cm:
            translator.translate("Hello", "en", "es")
        self.assertIn("Respuesta inesperada de DeepL", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
