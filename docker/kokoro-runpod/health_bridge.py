#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_PORT = int(os.getenv("KOKORO_PORT", os.getenv("PORT", "8880")))
HEALTH_PORT = int(os.getenv("PORT_HEALTH", "8888"))


def kokoro_ready() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{APP_PORT}/health",
            timeout=2,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


class HealthHandler(BaseHTTPRequestHandler):
    server_version = "AHOS-Kokoro-HealthBridge/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print("[health-bridge] " + (fmt % args), flush=True)

    def _json(self, status: int, payload: dict[str, object] | None = None) -> None:
        body = b""
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        if body:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in {"/ping", "/health"}:
            self._json(404, {"status": "not_found"})
            return

        if kokoro_ready():
            self._json(200, {"status": "healthy", "backend": "kokoro"})
        else:
            # RunPod Load Balancer treats 204 as "still initializing".
            self._json(204)


if __name__ == "__main__":
    print(
        f"[health-bridge] listening on 0.0.0.0:{HEALTH_PORT}; "
        f"checking Kokoro at 127.0.0.1:{APP_PORT}/health",
        flush=True,
    )
    ThreadingHTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler).serve_forever()
