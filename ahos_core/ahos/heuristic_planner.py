"""Heuristic work generation that needs no model and no network.

The model planner goes idle when endpoints are rate limited or the machine is
offline. A holding must still find work: this scanner reads the project tree and
turns concrete observations (missing accessibility metadata, oversized scripts,
unresolved TODOs, missing offline cache entries) into small, verifiable
objectives. It never invents work when the project is clean.
"""

from __future__ import annotations

import re
from pathlib import Path

MAX_OBJECTIVES = 3
MAX_FILE_BYTES = 2 * 1024 * 1024
BIG_SCRIPT_BYTES = 120_000

TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".md"}
SKIP_PARTS = {".git", "node_modules", "tools", "android", "ios", "data", "dist"}


def _files(root: Path, suffix: str) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob(f"*{suffix}"):
        if any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            found.append(path)
    return found


def _read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def scan(root: str | Path, limit: int = MAX_OBJECTIVES) -> list[str]:
    """Return up to ``limit`` concrete objectives for this project."""

    base = Path(root)
    if not base.is_dir():
        return []
    objectives: list[str] = []

    html_files = _files(base, ".html")
    index = base / "www" / "index.html"
    candidates = [index] if index.is_file() else html_files[:3]
    for path in candidates:
        text = _read(path).lower()
        if not text:
            continue
        relative = path.relative_to(base).as_posix()
        if 'lang=' not in text[:400]:
            objectives.append(f"{relative} dosyasina dil (lang) ozniteligi ekle")
        if 'name="viewport"' not in text and "name='viewport'" not in text:
            objectives.append(f"{relative} dosyasina viewport meta etiketi ekle")
        if 'charset' not in text[:600]:
            objectives.append(f"{relative} dosyasina charset meta etiketi ekle")

    for path in _files(base, ".js"):
        if path.stat().st_size > BIG_SCRIPT_BYTES:
            relative = path.relative_to(base).as_posix()
            objectives.append(f"{relative} dosyasini daha kucuk modullere ayir")
            break

    todo_hits = 0
    todo_file = ""
    for path in _files(base, ".js"):
        text = _read(path)
        if re.search(r"\b(TODO|FIXME)\b", text):
            todo_hits += 1
            todo_file = todo_file or path.relative_to(base).as_posix()
        if todo_hits >= 2:
            break
    if todo_hits:
        objectives.append(f"{todo_file} icindeki TODO/FIXME notlarini coz")

    precache = base / "www" / "precache.js"
    if precache.is_file():
        cached = _read(precache)
        missing = [
            path.relative_to(base).as_posix()
            for path in _files(base, ".js")
            if path.name not in cached and path.name not in {"precache.js"}
        ]
        if missing:
            objectives.append(f"cevrimdisi onbellege {missing[0]} dosyasini ekle")

    seen: set[str] = set()
    unique: list[str] = []
    for objective in objectives:
        key = objective.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(objective)
        if len(unique) >= limit:
            break
    return unique
