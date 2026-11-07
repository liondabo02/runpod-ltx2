"""Gerçek tarayıcı testi: Edge CDP ile Seksek menü → oyun → bitiş → yeniden başlatma."""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import requests
import websocket

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8790/"
OUT = Path(r"C:\actions-runner\_work\AHOS-GAME-SEKSEK\qa")
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = Path(r"C:\actions-runner\_work\AHOS-GAME-SEKSEK\games\seksek\screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)


class CDP:
    def __init__(self, url: str) -> None:
        self.ws = websocket.create_connection(url, timeout=15)
        self.next_id = 0
        self.events: list[dict] = []

    def send(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        message_id = self.next_id
        self.ws.send(json.dumps({"id": message_id, "method": method,
                                 "params": params or {}}))
        while True:
            raw = json.loads(self.ws.recv())
            if raw.get("id") == message_id:
                if "error" in raw:
                    raise RuntimeError(f"{method}: {raw['error']}")
                return raw.get("result") or {}
            if "method" in raw:
                self.events.append(raw)

    def evaluate(self, expression: str):
        result = self.send("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True})
        return result.get("result", {}).get("value")

    def shot(self, path: Path) -> None:
        data = self.send("Page.captureScreenshot", {"format": "png"})["data"]
        path.write_bytes(base64.b64decode(data))


def main() -> int:
    targets = requests.get("http://127.0.0.1:9222/json/list", timeout=5).json()
    page = next(item for item in targets if item.get("type") == "page")
    cdp = CDP(page["webSocketDebuggerUrl"])
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.send("Log.enable")
    cdp.send("Page.navigate", {"url": BASE})
    time.sleep(2.0)

    report: dict = {"url": BASE, "browser": "Edge headless CDP", "steps": []}

    def step(name: str, expression: str, wait: float = 0.6) -> None:
        value = cdp.evaluate(expression)
        time.sleep(wait)
        snap = cdp.evaluate("window.__qa ? __qa.snap() : null")
        report["steps"].append({"step": name, "value": value, "snap": snap})
        print(name, "->", value, "|", snap)

    report["title"] = cdp.evaluate("document.title")
    report["has_qa"] = cdp.evaluate("typeof window.__qa === 'object'")
    report["canvas"] = cdp.evaluate(
        "(()=>{const c=document.getElementById('cv');const r=c.getBoundingClientRect();"
        "return {w:c.width,h:c.height,cssW:Math.round(r.width),cssH:Math.round(r.height)};})()")
    cdp.shot(SHOTS / "01-menu.png")

    step("start", "__qa.start()", 1.2)
    cdp.shot(SHOTS / "02-gameplay.png")

    rect = cdp.evaluate(
        "(()=>{const r=document.getElementById('cv').getBoundingClientRect();"
        "return {x:r.x,y:r.y,w:r.width,h:r.height};})()")
    x = rect["x"] + rect["w"] * 0.5
    y = rect["y"] + rect["h"] * 0.72
    for event in ("mousePressed", "mouseReleased"):
        cdp.send("Input.dispatchMouseEvent", {"type": event, "x": x, "y": y,
                                              "button": "left", "clickCount": 1})
    time.sleep(0.5)
    report["after_click"] = cdp.evaluate("__qa.snap()")

    step("finish", "__qa.finish()", 0.8)
    cdp.shot(SHOTS / "03-finished.png")
    step("restart", "__qa.restart()", 0.8)
    cdp.shot(SHOTS / "04-restarted.png")

    errors = []
    for event in cdp.events:
        if event.get("method") == "Runtime.exceptionThrown":
            errors.append(event)
        elif event.get("method") == "Log.entryAdded":
            entry = event.get("params", {}).get("entry", {})
            url = str(entry.get("url") or "")
            if entry.get("level") == "error" and not url.startswith("chrome-extension://"):
                errors.append(event)
    report["runtime_errors"] = errors
    report["ok"] = bool(
        report["has_qa"] and report["steps"][0]["snap"] and report["steps"][0]["snap"]["running"]
        and report["steps"][1]["snap"] and not report["steps"][1]["snap"]["running"]
        and report["steps"][1]["snap"]["score"] == 30
        and report["steps"][2]["snap"] and report["steps"][2]["snap"]["running"]
        and report["steps"][2]["snap"]["score"] == 0
        and not errors)
    (OUT / "browser-test.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "title": report["title"],
                      "screenshots": [str(p) for p in sorted(SHOTS.glob("*.png"))],
                      "errors": len(errors)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
