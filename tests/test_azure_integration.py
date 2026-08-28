"""Tests de integración de Azure Translator con un servidor mock."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.models import ExtractedDocument, ExtractedFile, TranslationUnit
from epub_toolkit.translator import (
    AzureTranslator,
    QuotaExceededError,
    translate_batch_for_file,
    translate_document,
    translate_unit,
)


class MockAzureHandler(BaseHTTPRequestHandler):
    """Servidor mock que simula /translate de Azure Translator."""

    response_type: str = "ok"
    received_key: str | None = None
    received_region: str | None = None
    received_texts: list[dict[str, str]] | None = None

    def do_POST(self) -> None:
        MockAzureHandler.received_key = None
        MockAzureHandler.received_region = None
        MockAzureHandler.received_texts = None

        if not self.path.startswith("/translate"):
            self.send_response(404)
            self.end_headers()
            return

        MockAzureHandler.received_key = self.headers.get("Ocp-Apim-Subscription-Key")
        MockAzureHandler.received_region = self.headers.get("Ocp-Apim-Subscription-Region")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            MockAzureHandler.received_texts = data
            target = "es"

            if self.response_type == "quota":
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Rate limit/quota exceeded"}).encode("utf-8"))
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

            response = [
                {"translations": [{"text": f"[{target.upper()}] {item['Text']} [{target.upper()}]"}]}
                for item in data
            ]
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


class AzureIntegrationTestCase(unittest.TestCase):
    """Prueba el traductor de Azure contra un servidor local."""

    @classmethod
    def setUpClass(cls) -> None:
        MockAzureHandler.response_type = "ok"
        cls.server = HTTPServer(("127.0.0.1", 0), MockAzureHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    def tearDown(self) -> None:
        MockAzureHandler.response_type = "ok"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def _translator(self, **kwargs) -> AzureTranslator:
        defaults = {
            "base_url": f"http://127.0.0.1:{self.port}",
            "api_key": "test-key",
        }
        defaults.update(kwargs)
        return AzureTranslator(**defaults)

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

    def test_api_key_and_region_are_sent(self) -> None:
        translator = self._translator(api_key="secret-key", region="westeurope")
        translator.translate("Hello", "en", "es")
        self.assertEqual(MockAzureHandler.received_key, "secret-key")
        self.assertEqual(MockAzureHandler.received_region, "westeurope")

    def test_quota_exceeded(self) -> None:
        MockAzureHandler.response_type = "quota"
        translator = self._translator()
        with self.assertRaises(QuotaExceededError):
            translator.translate("Hello", "en", "es")

    def test_error_500(self) -> None:
        MockAzureHandler.response_type = "500"
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
