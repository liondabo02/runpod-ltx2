"""Offline independence audit for a project.

A holding company must run without the internet. This scanner reports the things
that break that promise: external URLs in shipped files, missing acceptance
gates, missing offline caches and missing basic accessibility metadata. It is
read-only; fixes belong to the worker.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".md"}
SKIP_PARTS = {".git", "node_modules", "android", "ios", "data", "dist", "build"}
MAX_FILE_BYTES = 2 * 1024 * 1024
EXTERNAL = re.compile(
    r"""(?:\bsrc\s*=\s*|<link[^>]*\bhref\s*=\s*)["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)
BARE_URL = re.compile(r"https?://[a-z0-9.-]+", re.IGNORECASE)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def audit(root: str | Path) -> dict:
    base = Path(root).resolve()
    findings: list[dict] = []
    external: list[str] = []
    scanned = 0

    for path in _iter_files(base):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        relative = path.relative_to(base).as_posix()
        if path.suffix.lower() in {".html", ".css", ".js", ".svg"}:
            for match in EXTERNAL.finditer(text):
                external.append(f"{relative} → {match.group(1)[:80]}")

    if external:
        findings.append(
            {
                "kind": "external_dependency",
                "severity": "high",
                "count": len(external),
                "samples": external[:5],
                "fix": "harici URL'leri yerel kopyayla değiştir veya kaldır",
            }
        )

    index = base / "www" / "index.html"
    if not index.is_file():
        index = base / "index.html"
    if index.is_file():
        text = index.read_text(encoding="utf-8", errors="replace")
        head = text[:2000].lower()
        for attribute in ("lang=", 'name="viewport"', "charset"):
            if attribute not in head:
                findings.append(
                    {
                        "kind": "missing_meta",
                        "severity": "medium",
                        "detail": attribute,
                        "fix": f"index.html içine {attribute} ekle",
                    }
                )

    gate = base / "tools" / "check_offline.py"
    if not gate.is_file():
        findings.append(
            {
                "kind": "no_acceptance_gate",
                "severity": "high",
                "fix": "tools/check_offline.py kabul testi ekle",
            }
        )

    precache = base / "www" / "precache.js"
    if (base / "www").is_dir() and not precache.is_file():
        findings.append(
            {
                "kind": "no_offline_cache",
                "severity": "medium",
                "fix": "precache.js ile çevrimdışı önbellek kur",
            }
        )

    return {
        "project": str(base),
        "scanned_files": scanned,
        "external_references": len(external),
        "findings": findings,
        "offline_ready": not any(
            item["severity"] == "high" for item in findings
        ),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    roots = [item for item in args if not item.startswith("-")]
    if not roots:
        print("kullanım: python -m ahos.offline_audit <proje> [<proje> ...] [--json]")
        return 2
    reports = [audit(root) for root in roots]
    if "--json" in args:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0
    for report in reports:
        state = "HAZIR" if report["offline_ready"] else "EKSİK"
        print(f"{state} · {report['project']} · {report['scanned_files']} dosya")
        for finding in report["findings"]:
            print(f"  - [{finding['severity']}] {finding['kind']}: {finding.get('fix') or finding.get('detail')}")
    return 0 if all(report["offline_ready"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
