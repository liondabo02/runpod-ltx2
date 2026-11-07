"""True UI end-to-end: actual pointer/touch events, eight legal rounds.

Uses only read-only __qa.snap() for assertions. Never invokes __qa.start,
__qa.finish or any synthetic game completion function.
"""
from __future__ import annotations
import base64
import json
import os
import sys
import time
from pathlib import Path
import requests
import websocket

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "qa"
SHOTS = ROOT / "games" / "seksek" / "screenshots"
BASE = os.environ.get("SEKSEK_BASE_URL", "http://127.0.0.1:8790/")


class CDP:
    def __init__(self, url: str):
        self.ws = websocket.create_connection(url, timeout=15)
        self.mid = 0
        self.events = []

    def send(self, method: str, params=None):
        self.mid += 1
        ident = self.mid
        self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            row = json.loads(self.ws.recv())
            if row.get("id") == ident:
                if row.get("error"):
                    raise RuntimeError(str(row["error"]))
                return row.get("result") or {}
            if row.get("method"):
                self.events.append(row)

    def eval(self, source: str):
        row = self.send("Runtime.evaluate", {"expression": source,
                                              "returnByValue": True, "awaitPromise": True})
        if row.get("exceptionDetails"):
            raise RuntimeError(str(row["exceptionDetails"]))
        return row.get("result", {}).get("value")

    def shot(self, filename: str):
        path = SHOTS / filename
        path.write_bytes(base64.b64decode(self.send("Page.captureScreenshot",
                                                    {"format": "png"})["data"]))
        return str(path)

    def click(self, x: float, y: float):
        for kind in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y,
                                                   "button": "left", "clickCount": 1})

    def touch(self, x: float, y: float):
        self.send("Input.dispatchTouchEvent", {"type": "touchStart",
                                              "touchPoints": [{"x": x, "y": y}]})
        self.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

    def rect(self, selector: str):
        return self.eval("(()=>{const e=document.querySelector("+json.dumps(selector)+");"
                         "e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();"
                         "return {x:r.x,y:r.y,w:r.width,h:r.height};})()")

    def button(self, selector: str, *, touch=False):
        r = self.rect(selector)
        x, y = r["x"] + r["w"]/2, r["y"] + r["h"]/2
        if touch:
            self.touch(x, y)
        else:
            self.click(x, y)

    def game_point(self, px: float, py: float, *, touch=False):
        rect = self.rect("#cv")
        x = rect["x"] + rect["w"] * px / 880
        y = rect["y"] + rect["h"] * py / 500
        if touch:
            self.touch(x, y)
        else:
            self.click(x, y)

    def snap(self):
        return self.eval("window.__qa.snap()")

    def until(self, predicate, timeout: float = 3.0):
        start = time.monotonic()
        while time.monotonic()-start < timeout:
            state = self.snap()
            if state and predicate(state):
                return state
            time.sleep(0.025)
        raise AssertionError(f"Timeout waiting for game state: {self.snap()}; events={self.events[-5:]}")


def main() -> int:
    targets = requests.get(os.environ.get("SEKSEK_CDP_URL", "http://127.0.0.1:9224/json/list"), timeout=4).json()
    pages = [x for x in targets if x.get("type") == "page"]
    assert pages
    c = CDP(pages[0]["webSocketDebuggerUrl"])
    for mode in ("Page.enable", "Runtime.enable", "Log.enable"):
        c.send(mode)
    c.send("Page.navigate", {"url": BASE})
    time.sleep(1)
    assert c.eval("document.title") == "Mipiluna · Seksek"
    assert c.eval("typeof __qa.finish") == "undefined", "Synthetic finish must be absent"
    c.button("#startBtn")
    started = c.until(lambda s: s["running"])
    assert started["score"] == 0 and started["lives"] == 3
    report = {"origin": BASE, "used_game_cheats": False, "started_by": "Input.dispatchMouseEvent",
              "steps": [], "start": started, "screenshots": []}
    for number in range(1,9):
        x = 140 + ((number-1)%4)*150
        y = 180 + ((number-1)//4)*150
        c.game_point(x,y)
        arrived = c.until(lambda s: s["game"]["phase"] == "hop"
                          and s["game"]["target"] == number)
        # The marker physically moves over the green range; input is a mouse event.
        c.until(lambda s: 0.43 <= s["game"]["marker"] <= 0.55, timeout=2.8)
        c.game_point(440,420)
        state = c.until(lambda s: s["game"]["target"] == number+1,
                        timeout=1.5)
        assert state["lives"] == 3 and state["score"] == (30 if number == 8 else 0), state
        report["steps"].append({"square": number, "arrived": arrived["game"]["phase"],
                                "after": state["game"]["phase"], "score": state["score"]})
        if number == 1:
            report["screenshots"].append(c.shot("07-playthrough-after-1.png"))
    won = c.snap()
    assert won["running"] is False and won["score"] == 30
    report["won"] = won
    report["screenshots"].append(c.shot("08-playthrough-won.png"))
    c.button("#startBtn")
    restarted = c.until(lambda s: s["running"] and s["score"] == 0)
    report["restarted"] = restarted
    report["screenshots"].append(c.shot("09-playthrough-restarted.png"))
    # A real incorrect throw must deduct one life, not silently grant success.
    c.game_point(590, 330)
    after_miss = c.until(lambda s: s["lives"] == 2 and s["game"]["phase"] == "aim")
    assert after_miss["score"] == 0 and after_miss["running"]
    report["wrong_throw"] = {"lives": after_miss["lives"], "score": after_miss["score"]}
    # Mobile real touch smoke: starts the game and enters the hop phase.
    c.send("Emulation.setDeviceMetricsOverride",
           {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
    c.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
    c.send("Page.navigate", {"url": BASE})
    time.sleep(1)
    mobile_dims = c.eval("({innerW:innerWidth,docW:document.documentElement.scrollWidth})")
    assert mobile_dims["docW"] <= mobile_dims["innerW"]+2, mobile_dims
    c.button("#startBtn", touch=True)
    c.until(lambda s: s["running"])
    c.game_point(140,180,touch=True)
    mobile = c.until(lambda s: s["game"]["phase"] == "hop"
                     and s["game"]["target"] == 1, timeout=3)
    report["mobile"] = {"viewport": mobile_dims, "touch_arrived": mobile["game"]["phase"]}
    report["screenshots"].append(c.shot("10-playthrough-mobile-touch.png"))
    errors = []
    for e in c.events:
        if e.get("method") == "Runtime.exceptionThrown":
            errors.append("runtime_exception")
        if e.get("method") == "Log.entryAdded":
            entry = e.get("params", {}).get("entry", {})
            if entry.get("level") == "error" and not str(entry.get("url") or "").startswith("chrome-extension://"):
                errors.append(str(entry)[:140])
    report["errors"] = errors
    report["ok"] = len(report["steps"]) == 8 and not errors
    (OUT/"real-browser-playthrough.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "rounds": len(report["steps"]),
                      "score": won["score"], "lives": won["lives"],
                      "restarted": restarted["score"] == 0,
                      "mobile": report["mobile"], "errors": errors},
                     ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
