"""Manual no-cost headless browser gate verification (not run in unit suite)."""
from pathlib import Path
from tempfile import TemporaryDirectory
from ahos.browser_check import check_page, find_browser

browser = find_browser()
print("BROWSER:", browser, flush=True)
if not browser:
    raise SystemExit("No browser: release QA must block")
with TemporaryDirectory(prefix="ahos-qa-") as tmp:
    root = Path(tmp)
    good = root / "ok.html"
    broken = root / "broken.html"
    good.write_text('<!doctype html><html><head><title>OK</title></head><body><main><h1>AHOS safe browser delivery</h1><button>Start</button></main></body></html>', encoding="utf-8")
    broken.write_text('<!doctype html><html><head><title>Broken</title></head><body><div id="root"></div><script>document.querySelector("#root").innerHTML = "";</script></body></html>', encoding="utf-8")
    for name, file in (("good", good), ("broken", broken)):
        result = check_page(file, root / (name + "-artifacts"), timeout=25)
        print(name, "PASS" if result.ok else "BLOCKED", result.summary(), result.screenshot, flush=True)
        if (name == "good") != result.ok:
            raise SystemExit(2)
print("BROWSER_QA_VERIFIED", flush=True)
