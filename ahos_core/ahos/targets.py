"""Görev metninden hedef dosya adlarını çıkarır.

Amaç: model çağrısından ÖNCE hedefin projede var olup olmadığını doğrulamak.
Yanlış dosya adı yüzünden 600 saniye beklemek yerine hızlı ve açık hata verilir.
"""

from __future__ import annotations

import re
from pathlib import Path

# .js, .css, .html, .py, .json, .md gibi uzantılı adlar; yol içerebilir.
_FILE_PATTERN = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:js|mjs|cjs|css|html|htm|py|json|md|txt|svg|png|jpg|webp|wav|mp3|mp4)")


def mentioned_files(task: str) -> tuple[str, ...]:
    """Görev metninde geçen dosya adlarını normalize ederek döndürür."""

    found: list[str] = []
    for match in _FILE_PATTERN.finditer(task or ""):
        raw = match.group(0).replace("\\", "/").lstrip("./")
        if not raw or raw in found:
            continue
        found.append(raw)
    return tuple(found)


def missing_targets(root: str | Path, task: str) -> tuple[str, ...]:
    """Metinde geçip projede bulunmayan dosyalar."""

    base = Path(root)
    missing: list[str] = []
    for relative in mentioned_files(task):
        candidate = base / relative
        if candidate.is_file():
            continue
        # Aynı ada sahip dosya başka klasörde olabilir (www/style.css vb.)
        if any(base.rglob(Path(relative).name)):
            continue
        missing.append(relative)
    return tuple(missing)


def suggest_targets(root: str | Path, task: str, limit: int = 3) -> tuple[str, ...]:
    """Eksik hedef yerine önerilecek gerçek dosyalar (ada göre yakınlık)."""

    base = Path(root)
    names = [Path(item).stem.casefold() for item in mentioned_files(task)]
    if not names:
        return ()
    scored: list[tuple[int, str]] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        stem = path.stem.casefold()
        for name in names:
            if name and (name in stem or stem in name):
                scored.append((abs(len(stem) - len(name)), rel))
                break
    scored.sort()
    result: list[str] = []
    for _, rel in scored:
        if rel not in result:
            result.append(rel)
        if len(result) >= limit:
            break
    return tuple(result)
