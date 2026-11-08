"""PWA readiness: an installable app that works without the network.

Installability needs the manifest linked from the page, a service worker that
registers, an offline cache and valid icons. These checks are read-only and run
on any project root.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REQUIRED_MANIFEST_FIELDS = ("name", "start_url", "display", "icons")


def _web_root(root: Path) -> Path:
    www = root / "www"
    return www if (www / "index.html").is_file() else root


def validate_pwa(root: str | Path) -> dict:
    base = Path(root)
    web = _web_root(base)
    index = web / "index.html"
    problems: list[str] = []

    text = index.read_text(encoding="utf-8", errors="replace") if index.is_file() else ""
    if not text:
        problems.append("index.html yok")
        return {"ready": False, "problems": problems, "web_root": str(web)}

    if "manifest.webmanifest" not in text and 'rel="manifest"' not in text:
        problems.append("manifest bağlı değil")
    if "serviceWorker" not in text:
        problems.append("service worker kaydı yok")

    manifest = web / "manifest.webmanifest"
    if not manifest.is_file():
        problems.append("manifest.webmanifest yok")
    else:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            problems.append("manifest geçersiz JSON")
        else:
            for field in REQUIRED_MANIFEST_FIELDS:
                if not payload.get(field):
                    problems.append(f"manifest alanı eksik: {field}")
            icons = payload.get("icons") or []
            if not icons:
                problems.append("manifest ikon listesi boş")
            else:
                for icon in icons:
                    source = str(icon.get("src") or "")
                    if source and not (web / source).is_file():
                        problems.append(f"ikon dosyası yok: {source}")

    worker = web / "sw.js"
    if not worker.is_file():
        problems.append("sw.js yok")
    else:
        worker_text = worker.read_text(encoding="utf-8", errors="replace")
        if "precache.js" not in worker_text and "CORE_ASSETS" not in worker_text:
            problems.append("service worker çevrimdışı önbellek kurmuyor")
        if not re.search(r"addEventListener\(\s*['\"]fetch['\"]", worker_text):
            problems.append("service worker fetch yakalamıyor")

    if not (web / "precache.js").is_file():
        problems.append("precache.js yok")

    return {"ready": not problems, "problems": problems, "web_root": str(web)}


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("kullanım: python -m ahos.pwa <proje>")
        return 2
    result = validate_pwa(args[0])
    print(("HAZIR" if result["ready"] else "EKSİK") + f" · {result['web_root']}")
    for problem in result["problems"]:
        print("  -", problem)
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
