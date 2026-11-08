"""Capture a screenshot of the live office page (for reports/evidence)."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

URL = "http://127.0.0.1:8799/"
OUT = Path(__file__).resolve().parents[2] / "quality" / "evidence" / "office.png"


def _browser() -> list[str]:
    import shutil

    for name in ("msedge", "chrome"):
        found = shutil.which(name)
        if found:
            return [found]
    for candidate in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ):
        if Path(candidate).is_file():
            return [candidate]
    raise SystemExit("tarayıcı bulunamadı")


def main() -> int:
    port = 9334
    profile = Path(tempfile.mkdtemp(prefix="ahos-shot-"))
    browser = subprocess.Popen(
        [
            *_browser(),
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--disable-gpu",
            "--remote-allow-origins=*",
            "--window-size=1400,900",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = ""
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                    pages = [item for item in json.loads(response.read().decode()) if item.get("type") == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws_url:
            print("sayfa hedefi yok")
            return 2

        ws = websocket.create_connection(ws_url, timeout=30)
        counter = 0

        def call(method: str, params: dict | None = None):
            nonlocal counter
            counter += 1
            ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            while True:
                message = json.loads(ws.recv())
                if message.get("id") == counter:
                    return message.get("result", {})

        call("Page.enable")
        call("Page.navigate", {"url": URL})
        time.sleep(4.0)
        shot = call("Page.captureScreenshot", {"format": "png"})
        data = shot.get("data") or ""
        if not data:
            print("ekran görüntüsü alınamadı")
            return 1
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_bytes(base64.b64decode(data))
        print(f"kaydedildi: {OUT} ({OUT.stat().st_size} bayt)")
        return 0
    finally:
        try:
            browser.terminate()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
