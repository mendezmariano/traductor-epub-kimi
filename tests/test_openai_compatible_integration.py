"""Test de integración de OpenAICompatibleTranslator con un servidor mock."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.models import TranslationUnit
from epub_toolkit.translator import OpenAICompatibleTranslator, translate_unit


class MockOpenAIHandler(BaseHTTPRequestHandler):
    """Servidor mock que simula /chat/completions de OpenAI."""

    def do_POST(self) -> None:
        if self.path != "/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            messages = data.get("messages", [])
            user_message = messages[-1]["content"] if messages else ""

            # Buscamos líneas numeradas en el prompt y devolvemos traducciones simuladas.
            translations: list[str] = []
            for line in user_message.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Líneas numeradas como "1. Hello world"
                if len(line) > 2 and line[0].isdigit() and line[1] == ".":
                    text = line[2:].strip()
                    translations.append(f"{len(translations) + 1}. [ES] {text} [ES]")

            if not translations:
                translations = ["1. [ES] Traducción [ES]"]

            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "\n".join(translations),
                        }
                    }
                ]
            }
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


class OpenAICompatibleIntegrationTestCase(unittest.TestCase):
    """Prueba el traductor OpenAI-compatible contra un servidor local."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), MockOpenAIHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_translate_via_mock(self) -> None:
        translator = OpenAICompatibleTranslator(
            api_key="test-key",
            base_url=f"http://127.0.0.1:{self.port}",
            model="gpt-4o-mini",
        )
        result = translator.translate("Hello world", "en", "es")
        self.assertIn("[ES]", result)

    def test_translate_unit_preserves_placeholders(self) -> None:
        unit = TranslationUnit(
            unit_id="u1",
            xpath="//p[1]",
            original="Hello {ph0}world{ph0}.",
            placeholders={"{ph0}": {"tag": "b", "attrs": {}, "self_closing": False}},
        )
        translator = OpenAICompatibleTranslator(
            api_key="test-key",
            base_url=f"http://127.0.0.1:{self.port}",
            model="gpt-4o-mini",
        )
        result = translate_unit(translator, unit, "en", "es")
        self.assertIn("{ph0}", result)
        self.assertIn("world", result)
        self.assertIn("[ES]", result)


if __name__ == "__main__":
    unittest.main()
