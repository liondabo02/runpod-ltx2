"""Görev hedefini projede var olan gerçek dosyaya çözer.

Ölçüm: uzman mühendisin başarısızlıklarının **%56'sı** "hedef dosya yok"
(41/73). Model, projede olmayan bir adı (ör. `www/style.css`) hedef seçiyor ve
yama uygulanamıyor. Çözüm: görev metnindeki var olmayan dosya adlarını, projedeki
en yakın gerçek dosyayla değiştirmek — modelin uydurmasına fırsat vermeden.
"""

from __future__ import annotations

import re
from pathlib import Path

from .targets import mentioned_files

_TEXT_SUFFIXES = {".js", ".css", ".html", ".py", ".json", ".md", ".txt"}


def _real_files(root: Path) -> list[str]:
    result: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "__pycache__", "android", "ios"} for part in path.parts):
            continue
        if path.suffix.lower() in _TEXT_SUFFIXES:
            result.append(path.relative_to(root).as_posix())
    return result


def _best_match(missing: str, real_files: list[str]) -> str | None:
    wanted = Path(missing).name.casefold()
    stem = Path(missing).stem.casefold()
    suffix = Path(missing).suffix.casefold()

    scored: list[tuple[int, str]] = []
    for candidate in real_files:
        name = Path(candidate).name.casefold()
        candidate_stem = Path(candidate).stem.casefold()
        score = 0
        if name == wanted:
            score = 100
        elif candidate_stem == stem:
            score = 90
        elif suffix and Path(candidate).suffix.casefold() == suffix and stem in candidate_stem:
            score = 70
        elif stem and (stem in candidate_stem or candidate_stem in stem):
            score = 50
        if score:
            scored.append((score, candidate))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    return scored[0][1]


def resolve_objective(root: str | Path, objective: str, *, append_hint: bool = True) -> tuple[str, tuple[str, ...]]:
    """Görev metnini gerçek dosya adlarıyla düzeltir.

    Döndürür: (yeni görev metni, değiştirilen hedefler)
    Değişiklik yoksa metin aynen döner.
    """

    base = Path(root)
    files = _real_files(base)
    if not files:
        return objective, ()

    replaced: list[str] = []
    text = objective
    for missing in mentioned_files(objective):
        candidate = base / missing
        if candidate.is_file():
            continue
        match = _best_match(missing, files)
        if match is None:
            continue
        text = text.replace(missing, match)
        replaced.append(f"{missing} → {match}")

    if replaced and append_hint:
        text = text.rstrip() + "\n\n(Gerçek hedef dosya: " + replaced[0].split("→")[-1].strip() + ")"
    return text, tuple(replaced)
