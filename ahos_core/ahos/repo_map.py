"""Repo haritası — Aider'ın `--map-tokens` deseninin sadeleştirilmiş hâli.

Amaç: modele **tüm dosya listesi** yerine, göreve en yakın dosyaları ve
içlerindeki tanımları (fonksiyon/sınıf/sabit) vermek. Böylece istem küçülür,
model doğru dosyayı seçer.

Saf metin tarama; model/embedding gerekmez.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IGNORED = {".git", "node_modules", "__pycache__", ".venv", "android", "ios", "build", "dist", ".gradle"}
TEXT_SUFFIXES = {".py", ".js", ".mjs", ".ts", ".css", ".html", ".json", ".md"}

_PATTERNS = (
    ("def", re.compile(r"^\s*def\s+([A-Za-z_]\w*)")),
    ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)")),
    ("function", re.compile(r"^\s*(?:async\s+)?function\s+([A-Za-z_]\w*)")),
    ("const", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=")),
    ("var", re.compile(r"^\s*var\s+([A-Za-z_]\w*)\s*=")),
    ("selector", re.compile(r"^([.#][A-Za-z][\w-]*)\s*\{")),
)


@dataclass(frozen=True)
class FileMap:
    path: str
    size: int
    symbols: tuple[str, ...]


def _symbols(path: Path, limit: int = 8) -> tuple[str, ...]:
    found: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    for line in text.splitlines()[:4000]:
        for kind, pattern in _PATTERNS:
            match = pattern.match(line)
            if match:
                found.append(f"{match.group(1)}")
                break
        if len(found) >= limit:
            break
    return tuple(found[:limit])


def scan(root: str | Path, *, max_files: int = 400) -> list[FileMap]:
    """Depoyu tarar; her dosya için boyut ve ilk tanımları çıkarır."""

    base = Path(root)
    result: list[FileMap] = []
    for path in base.rglob("*"):
        if len(result) >= max_files:
            break
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if set(path.parts) & IGNORED:
            continue
        result.append(
            FileMap(
                path=path.relative_to(base).as_posix(),
                size=path.stat().st_size,
                symbols=_symbols(path),
            )
        )
    return result


def rank(maps: list[FileMap], task: str, *, limit: int = 8) -> list[FileMap]:
    """Görev metniyle dosya adı/sembol örtüşmesine göre sıralar."""

    words = {w.casefold() for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9_]{3,}", task)}
    scored: list[tuple[int, FileMap]] = []
    for item in maps:
        name = item.path.casefold()
        score = 0
        for word in words:
            if word in name:
                score += 10
            if any(word == symbol.casefold() for symbol in item.symbols):
                score += 6
            elif any(word in symbol.casefold() for symbol in item.symbols):
                score += 2
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].size))
    return [item for _, item in scored[:limit]]


def repo_map_text(root: str | Path, task: str, *, limit: int = 8, max_files: int = 400) -> str:
    """İstem için kısa depo haritası metni (`- yol: semboller`)."""

    maps = scan(root, max_files=max_files)
    if not maps:
        return ""
    chosen = rank(maps, task, limit=limit) or sorted(maps, key=lambda m: m.size)[:limit]
    lines = ["### Depo haritası (göreve en yakın dosyalar)"]
    for item in chosen:
        symbols = ", ".join(item.symbols[:6]) or "-"
        lines.append(f"- {item.path} ({item.size} B): {symbols}")
    return "\n".join(lines)
