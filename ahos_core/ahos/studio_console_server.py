"""Stüdyo konsolu için küçük HTTP sunucu (mevcut ofis sunucusuna dokunmaz).

Kullanım:
    python -m ahos.studio_console_server            # http://127.0.0.1:8770/studio

Sayfa: konu kutusu + süre/dil/bölüm + ÜRET düğmesi. Üretim arka planda
`ahos.series_cli` ile çalışır; sayfa 2 sn'de bir durum sorar, bitince videoyu oynatır.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import studio_console as console

DEFAULT_PORT = 8770


class StudioHandler(BaseHTTPRequestHandler):  # noqa: N801 - stdlib naming
    server_version = "AHOSStudioConsole/1.0"

    def _send(self, code: int, body, content_type: str = "application/json; charset=utf-8") -> None:
        payload = body.encode("utf-8") if isinstance(body, str) else bytes(body)
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args) -> None:  # sessiz: konsolu kirletme
        return

    def do_GET(self):  # noqa: N802 - stdlib naming
        route = urlsplit(self.path).path
        if route in ("/", "/studio"):
            self._send(200, console.PRODUCE_PAGE, "text/html; charset=utf-8")
            return
        if route == "/api/studio/status":
            job_id = (parse_qs(urlsplit(self.path).query).get("id") or [""])[0]
            status = console.refresh_job(job_id) if job_id else None
            self._send(200, json.dumps(status or {"status": "UNKNOWN"}, ensure_ascii=False))
            return
        if route == "/api/studio/video":
            job_id = (parse_qs(urlsplit(self.path).query).get("id") or [""])[0]
            path = console.video_path(job_id) if job_id else None
            if path is None:
                self._send(404, json.dumps({"error": "video yok"}))
                return
            self._send(200, path.read_bytes(), "video/mp4")
            return
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):  # noqa: N802 - stdlib naming
        route = urlsplit(self.path).path
        if route != "/api/studio/produce":
            self._send(404, json.dumps({"error": "not found"}))
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send(400, json.dumps({"error": "geçersiz JSON"}, ensure_ascii=False))
            return
        if not isinstance(body, dict):
            self._send(400, json.dumps({"error": "gövde nesne olmalı"}, ensure_ascii=False))
            return
        try:
            result = console.start_job(
                body.get("topic", ""),
                minutes=float(body.get("minutes") or 9),
                language=str(body.get("language") or "tr"),
                episode=int(body.get("episode") or 1),
            )
        except (ValueError, TypeError) as exc:
            self._send(400, json.dumps({"error": str(exc)}, ensure_ascii=False))
            return
        self._send(200, json.dumps(result, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="ahos-studio-console",
                                     description="Konu yaz, bölüm üret, videoyu tarayıcıda izle")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, int(args.port)), StudioHandler)
    print(f"Stüdyo konsolu hazır: http://{args.host}:{args.port}/studio  (Ctrl+C ile çık)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
