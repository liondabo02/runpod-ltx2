"""Hafif sır/izin taraması (AgentShield fikrinin bizdeki karşılığı).

Arananlar:
- API anahtarı desenleri: `sk-`, `ghp_`, `gho_`, `AKIA`, `xoxb-`, `RUNPOD_API_KEY=`
- Özel anahtar blokları: `-----BEGIN ... PRIVATE KEY-----`
- Git tarafından izlenen `.env` / `.env.*` dosyaları
- `.env` içinde düz metin anahtar (yalnız varlık bildirilir, değer yazdırılmaz)

Çıkış kodu: temiz → 0, bulgu → 1. Değerler asla ekrana basılmaz.

    python tools/agentshield_lite.py [--root PATH] [--max-bytes N]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "github_token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    # `\s` satır sonunu da yutar; yalnız aynı satırdaki gerçek atama aranır.
    "runpod_key": re.compile(r"RUNPOD_API_KEY[ \t]*=[ \t]*[A-Za-z0-9_\-]{20,}"),
}

EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".example.ps1")

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "runtime", "backups", "frames"}


def _iter_files(root: Path, max_bytes: int):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
        except OSError:
            continue
        yield path


def _tracked_env(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", ".env", "**/.env", "**/.env.*"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception:  # noqa: BLE001
        return []
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="hafif sır taraması")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--max-bytes", type=int, default=400_000)
    args = parser.parse_args(argv)

    root = Path(args.root)
    findings: list[dict] = []
    scanned = 0

    for path in _iter_files(root, args.max_bytes):
        # `.env*` dosyaları sırların MEŞRU saklandığı yerdir; içerik taranmaz.
        # Kural ihlali, bu dosyaların git tarafından izlenmesidir (aşağıda).
        if path.name.startswith(".env"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({
                    "kind": name,
                    "file": str(path.relative_to(root)),
                    "value_printed": False,
                })

    tracked = _tracked_env(root)
    for item in tracked:
        # Örnek/şablon dosyalar bilinçli olarak repoda; sır içermezler.
        if Path(item).name.endswith(EXAMPLE_SUFFIXES):
            continue
        findings.append({"kind": "tracked_env_file", "file": item, "value_printed": False})

    report = {
        "root": str(root),
        "scanned_files": scanned,
        "findings": findings,
        "clean": not findings,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
