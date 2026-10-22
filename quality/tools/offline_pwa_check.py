"""Real offline proof: load the PWA, go offline, reload, expect the app to render.

Serves the web root over localhost (service workers need http), drives headless
Edge/Chrome through CDP, waits for the service worker, emulates an offline
network and reloads. Read-only for the project.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websocket


def _serve(directory: Path):
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/index.html"


def _find_browser() -> list[str]:
    import shutil

    for name in ("msedge", "chrome"):
        path = shutil.which(name)
        if path:
            return [path]
    for candidate in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        if Path(candidate).is_file():
            return [candidate]
    raise SystemExit("tarayıcı bulunamadı")


class _CDP:
    def __init__(self, ws_url: str) -> None:
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.counter = 0

    def call(self, method: str, params: dict | None = None):
        self.counter += 1
        self.ws.send(json.dumps({"id": self.counter, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == self.counter:
                return message.get("result", {})

    def eval(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        return result.get("result", {}).get("value")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else Path("ahos_core/runtime/projects/mipiluna/www")
    server, url = _serve(root)
    profile = Path(tempfile.mkdtemp(prefix="ahos-pwa-"))
    port = 9333
    browser = subprocess.Popen(
        [
            *_find_browser(),
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--remote-allow-origins=*",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as response:
                    info = json.loads(response.read().decode())
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("tarayıcı hata ayıklama portu açılmadı")
            return 2

        ws_url = ""
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                    targets = json.loads(response.read().decode())
                pages = [item for item in targets if item.get("type") == "page"]
                if pages:
                    ws_url = pages[0].get("webSocketDebuggerUrl", "")
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws_url:
            print("sayfa hedefi bulunamadı")
            return 2
        cdp = _CDP(ws_url)
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Page.navigate", {"url": url})
        time.sleep(3.0)

        ready = cdp.eval(
            "navigator.serviceWorker.ready.then(function(r){return !!r.active;}).catch(function(){return false;})"
        )
        if not ready:
            # İlk yükleme kaydı yapmış olabilir; kısa bir bekleme daha.
            time.sleep(2.0)
            ready = cdp.eval("navigator.serviceWorker.controller ? true : false")
        online_text = cdp.eval("document.body ? document.body.innerText.length : 0") or 0

        cdp.call("Network.enable")
        cdp.call(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
            },
        )
        cdp.call("Page.reload", {"ignoreCache": False})
        time.sleep(3.0)
        offline_text = cdp.eval("document.body ? document.body.innerText.length : 0") or 0
        title = cdp.eval("document.title || ''")

        print(f"service worker: {'aktif' if ready else 'yok'}")
        print(f"çevrimiçi metin: {online_text} karakter")
        print(f"çevrimdışı metin: {offline_text} karakter")
        print(f"başlık: {title}")
        ok = bool(ready) and offline_text > 100
        print("SONUÇ:", "çevrimdışı çalışıyor" if ok else "çevrimdışı başarısız")
        return 0 if ok else 1
    finally:
        try:
            browser.terminate()
        except Exception:  # noqa: BLE001 - teardown must not mask the verdict
            pass
        try:
            server.shutdown()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
