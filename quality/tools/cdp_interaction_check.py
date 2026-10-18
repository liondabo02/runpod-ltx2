"""Real interaction evidence for Mipiluna via the Chrome DevTools Protocol.

Loads the page in headless Edge, dismisses the language dialog, clicks the first
game card and records what actually happened (scene change, console errors,
screenshot). This is an evidence tool, not part of the pytest suite: it needs a
browser and the optional ``websocket-client`` package.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websocket

PORT = 9333
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def _browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).exists():
            return candidate
    raise SystemExit("tarayıcı bulunamadı")


class Cdp:
    def __init__(self, ws_url: str) -> None:
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.next_id = 0
        self.events: list[dict] = []

    def call(self, method: str, **params):
        self.next_id += 1
        ident = self.next_id
        self.ws.send(json.dumps({"id": ident, "method": method, "params": params}))
        deadline = time.time() + 30
        while time.time() < deadline:
            message = json.loads(self.ws.recv())
            if message.get("id") == ident:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            if "method" in message:
                self.events.append(message)
        raise TimeoutError(method)

    def eval(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            expression=expression,
            returnByValue=True,
            awaitPromise=True,
        )
        return result.get("result", {}).get("value")

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read())


def _put(url: str) -> dict:
    request = urllib.request.Request(url, method="PUT")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def run(page: Path, artifacts: Path) -> dict:
    artifacts.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="cdp-profile-"))
    binary = _browser()
    process = subprocess.Popen(
        [
            binary,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        version = None
        for _ in range(60):
            try:
                version = _get(f"http://127.0.0.1:{PORT}/json/version")
                break
            except Exception:
                time.sleep(0.25)
        if version is None:
            raise SystemExit("CDP başlatılamadı")

        url = "file:///" + page.resolve().as_posix().lstrip("/")
        target = _put(f"http://127.0.0.1:{PORT}/json/new?{urllib.parse.quote(url, safe='')}")
        ws_url = target["webSocketDebuggerUrl"]
        client = Cdp(ws_url)
        client.call("Runtime.enable")
        client.call("Page.enable")

        # Sayfa ve kartlar hazır olana kadar bekle.
        deadline = time.time() + 30
        cards = 0
        while time.time() < deadline:
            cards = client.eval("document.querySelectorAll('.card').length") or 0
            if cards:
                break
            time.sleep(0.5)

        # İlk yüklemede yetişkin ayarları <dialog> olarak açılıyor; kapat.
        deadline = time.time() + 10
        while time.time() < deadline:
            if client.eval("document.querySelector('dialog[open]') ? 1 : 0"):
                break
            time.sleep(0.4)
        dialog = client.eval(
            "(() => { const d = document.querySelector('dialog[open]');"
            " return d ? (d.querySelector('h2,h3,strong')?.textContent || 'dialog').slice(0, 40) : null; })()"
        )
        picked = client.eval(
            "(() => { const d = document.querySelector('dialog[open]');"
            " if (!d) return null; d.close(); return 'closed'; })()"
        )
        time.sleep(0.8)
        dialog_after = client.eval(
            "document.querySelector('dialog[open]') ? 'visible' : null"
        )

        before = client.eval(
            "({scroll: document.querySelector('.card')?.dataset.game || null,"
            " scene: document.body.dataset.scene || null,"
            " title: document.querySelector('h1,h2')?.textContent || ''})"
        )
        clicked = client.eval(
            "(() => { const card = document.querySelector('.card');"
            " if (!card) return null;"
            " const label = (card.querySelector('b,strong,h3')?.textContent || card.textContent || '').trim().slice(0, 40);"
            " card.click(); return label; })()"
        )
        time.sleep(2.0)
        after = client.eval(
            "({scene: document.body.dataset.scene || null,"
            " hash: location.hash,"
            " stage: (document.querySelector('.stage')?.textContent || '').trim().slice(0, 80),"
            " overlays: document.querySelectorAll('.overlay,.modal,.dialog').length})"
        )
        errors = [
            event for event in client.events
            if event.get("method") == "Runtime.exceptionThrown"
        ]
        console_errors = [
            event for event in client.events
            if event.get("method") == "Runtime.consoleAPICalled"
            and event.get("params", {}).get("type") == "error"
        ]

        shot = client.call("Page.captureScreenshot", format="png")
        import base64

        (artifacts / "interaction.png").write_bytes(base64.b64decode(shot["data"]))
        client.close()

        return {
            "cards": cards,
            "dialog": dialog,
            "dialog_after": dialog_after,
            "dialog_action": picked,
            "clicked_card": clicked,
            "before": before,
            "after": after,
            "exceptions": len(errors),
            "console_errors": len(console_errors),
            "screenshot": str(artifacts / "interaction.png"),
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    page = Path(
        r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\index.html"
    )
    artifacts = Path(__file__).resolve().parent / "interaction-artifacts"
    result = run(page, artifacts)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = (
        result["cards"] > 0
        and result["clicked_card"]
        and result["exceptions"] == 0
        and result["console_errors"] == 0
    )
    print("INTERACTION_OK" if ok else "INTERACTION_PROBLEM")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
