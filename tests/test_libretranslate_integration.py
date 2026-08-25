"""Test de integración de LibreTranslate con un servidor mock."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.models import TranslationUnit
from epub_toolkit.translator import LibreTranslateTranslator, translate_unit


class MockLibreTranslateHandler(BaseHTTPRequestHandler):
    """Servidor mock que simula /translate de LibreTranslate."""

    def do_POST(self) -> None:
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
            marker = f"[{target.upper()}]"
            # Simulamos traducción; si q es lista, devolvemos lista.
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
        cls.server = HTTPServer(("127.0.0.1", 0), MockLibreTranslateHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_translate_via_mock(self) -> None:
        translator = LibreTranslateTranslator(
            base_url=f"http://127.0.0.1:{self.port}",
            delay=0,
        )
        result = translator.translate("Hello world", "en", "es")
        self.assertEqual(result, "[ES] Hello world [ES]")

    def test_translate_unit_preserves_placeholders(self) -> None:
        unit = TranslationUnit(
            unit_id="u1",
            xpath="//p[1]",
            original="Hello {ph0}world{ph0}.",
            placeholders={"{ph0}": {"tag": "b", "attrs": {}, "self_closing": False}},
        )
        translator = LibreTranslateTranslator(
            base_url=f"http://127.0.0.1:{self.port}",
            delay=0,
        )
        result = translate_unit(translator, unit, "en", "es")
        self.assertIn("{ph0}", result)
        self.assertIn("world", result)
        self.assertTrue(result.startswith("[ES]") and result.endswith("[ES]"))


if __name__ == "__main__":
    unittest.main()
