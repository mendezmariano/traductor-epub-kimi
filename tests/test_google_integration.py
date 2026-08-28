"""Tests de integración de Google Cloud Translation con un servidor mock."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.models import ExtractedDocument, ExtractedFile, TranslationUnit
from epub_toolkit.translator import (
    GoogleTranslator,
    QuotaExceededError,
    translate_batch_for_file,
    translate_document,
    translate_unit,
)


class MockGoogleHandler(BaseHTTPRequestHandler):
    """Servidor mock que simula Google Cloud Translation API."""

    response_type: str = "ok"
    received_key: str | None = None
    received_texts: list[str] | None = None

    def do_POST(self) -> None:
        MockGoogleHandler.received_key = None
        MockGoogleHandler.received_texts = None

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        MockGoogleHandler.received_key = params.get("key", [None])[0]

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            texts = data.get("q", [])
            target = data.get("target", "es")
            MockGoogleHandler.received_texts = texts

            if self.response_type == "quota":
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": {"message": "Quota exceeded"}}).encode("utf-8"))
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
                translated = [{"translatedText": f"[{target.upper()}] {t} [{target.upper()}]"} for t in texts]
            else:
                translated = [{"translatedText": f"[{target.upper()}] {texts} [{target.upper()}]"}]
            response = {"data": {"translations": translated}}
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


class GoogleIntegrationTestCase(unittest.TestCase):
    """Prueba el traductor de Google contra un servidor local."""

    @classmethod
    def setUpClass(cls) -> None:
        MockGoogleHandler.response_type = "ok"
        cls.server = HTTPServer(("127.0.0.1", 0), MockGoogleHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    def tearDown(self) -> None:
        MockGoogleHandler.response_type = "ok"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _translator(self, **kwargs) -> GoogleTranslator:
        defaults = {
            "base_url": f"http://127.0.0.1:{self.port}",
            "api_key": "test-key",
        }
        defaults.update(kwargs)
        return GoogleTranslator(**defaults)

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

    def test_api_key_is_sent(self) -> None:
        translator = self._translator(api_key="secret-key")
        translator.translate("Hello", "en", "es")
        self.assertEqual(MockGoogleHandler.received_key, "secret-key")

    def test_quota_exceeded(self) -> None:
        MockGoogleHandler.response_type = "quota"
        translator = self._translator()
        with self.assertRaises(QuotaExceededError):
            translator.translate("Hello", "en", "es")

    def test_error_500(self) -> None:
        MockGoogleHandler.response_type = "500"
        translator = self._translator()
        with self.assertRaises(RuntimeError):
            translator.translate("Hello", "en", "es")

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


if __name__ == "__main__":
    unittest.main()
