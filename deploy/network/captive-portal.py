#!/usr/bin/env python3
"""Minimaler Captive-Portal-Responder für den lokalen Kassen-Hotspot.

DNS zeigt im Hotspot auf den Pi. Dieses Script beantwortet HTTP auf Port 80 und
leitet typische Portal-Checks sowie normale Browseraufrufe zur Kasse weiter.
"""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


TARGET = os.environ.get("VK_CAPTIVE_TARGET", "http://kasse.local:8000").rstrip("/")
LISTEN = os.environ.get("VK_CAPTIVE_LISTEN", "0.0.0.0")
PORT = int(os.environ.get("VK_CAPTIVE_PORT", "80"))


class Handler(BaseHTTPRequestHandler):
    server_version = "VereinskasseCaptive/1.0"

    def do_GET(self) -> None:  # noqa: N802
        self._answer()

    def do_HEAD(self) -> None:  # noqa: N802
        self._redirect()

    def _answer(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/generate_204", "/gen_204", "/mobile/status.php", "/ncsi.txt", "/connecttest.txt"}:
            self._redirect()
            return
        html = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url={TARGET}">
  <title>Vereinskasse öffnen</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; min-height: 100vh; display: grid; place-items: center; background: #eef1f5; color: #0f172a; }}
    main {{ width: min(480px, calc(100vw - 32px)); background: white; border: 1px solid #cdd5e0; border-radius: 18px; padding: 24px; box-shadow: 0 12px 30px rgba(15,23,42,.12); }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    p {{ color: #475569; }}
    a {{ display: inline-flex; min-height: 48px; align-items: center; justify-content: center; padding: 0 18px; border-radius: 12px; background: #4f46e5; color: white; text-decoration: none; font-weight: 800; }}
  </style>
</head>
<body>
  <main>
    <h1>Vereinskasse</h1>
    <p>Die Kasse wird geöffnet. Falls nichts passiert, tippe auf den Button.</p>
    <a href="{TARGET}">Kasse öffnen</a>
  </main>
</body>
</html>"""
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self) -> None:
        self.send_response(302)
        self.send_header("Location", TARGET)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        if os.environ.get("VK_CAPTIVE_LOG", "0") == "1":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    ThreadingHTTPServer((LISTEN, PORT), Handler).serve_forever()
