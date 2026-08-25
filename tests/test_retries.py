"""Tests para la lógica de reintentos de traductores API."""

from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from epub_toolkit.translator import LibreTranslateTranslator


class FlakyLibreTranslateHandler(BaseHTTPRequestHandler):
    """Servidor mock que falla las primeras N peticiones y luego responde."""

    fail_count: int = 0
    success_after: int = 2
    fail_code: int = 500

    def do_POST(self) -> None:
        if self.path != "/translate":
            self.send_response(404)
            self.end_headers()
            return

        FlakyLibreTranslateHandler.fail_count += 1
        if FlakyLibreTranslateHandler.fail_count <= FlakyLibreTranslateHandler.success_after:
            self.send_response(FlakyLibreTranslateHandler.fail_code)
            self.end_headers()
            self.wfile.write(b"Server error")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            texts = data.get("q", "")
            target = data.get("target", "es")
            marker = f"[{target.upper()}]"
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


class RetryTestCase(unittest.TestCase):
    """Prueba reintentos ante fallos transitorios."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), FlakyLibreTranslateHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    def tearDown(self) -> None:
        FlakyLibreTranslateHandler.fail_count = 0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_retry_succeeds_after_transient_failures(self) -> None:
        FlakyLibreTranslateHandler.success_after = 2
        FlakyLibreTranslateHandler.fail_code = 500

        # Evitamos esperar los segundos reales de backoff.
        original_sleep = time.sleep
        time.sleep = lambda _: None  # type: ignore[assignment]
        try:
            translator = LibreTranslateTranslator(
                base_url=f"http://127.0.0.1:{self.port}",
                delay=0,
                retries=3,
            )
            result = translator.translate("Hello", "en", "es")
            self.assertEqual(result, "[ES] Hello [ES]")
            self.assertEqual(FlakyLibreTranslateHandler.fail_count, 3)
        finally:
            time.sleep = original_sleep  # type: ignore[assignment]

    def test_retry_fails_after_exhausted_retries(self) -> None:
        FlakyLibreTranslateHandler.success_after = 5
        FlakyLibreTranslateHandler.fail_code = 500

        original_sleep = time.sleep
        time.sleep = lambda _: None  # type: ignore[assignment]
        try:
            translator = LibreTranslateTranslator(
                base_url=f"http://127.0.0.1:{self.port}",
                delay=0,
                retries=2,
            )
            with self.assertRaises(RuntimeError):
                translator.translate("Hello", "en", "es")
            self.assertEqual(FlakyLibreTranslateHandler.fail_count, 3)
        finally:
            time.sleep = original_sleep  # type: ignore[assignment]

    def test_no_retry_on_client_error(self) -> None:
        FlakyLibreTranslateHandler.success_after = 5
        FlakyLibreTranslateHandler.fail_code = 400

        original_sleep = time.sleep
        time.sleep = lambda _: None  # type: ignore[assignment]
        try:
            translator = LibreTranslateTranslator(
                base_url=f"http://127.0.0.1:{self.port}",
                delay=0,
                retries=3,
            )
            with self.assertRaises(RuntimeError) as cm:
                translator.translate("Hello", "en", "es")
            self.assertIn("Error HTTP (400)", str(cm.exception))
            self.assertEqual(FlakyLibreTranslateHandler.fail_count, 1)
        finally:
            time.sleep = original_sleep  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
