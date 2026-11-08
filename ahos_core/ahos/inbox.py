"""Inbox: drop documents in a folder, the holding learns from them.

The owner should not have to run commands. Anything placed in
``runtime/knowledge/inbox`` is picked up automatically: indexed into the
knowledge network, turned into skill cards and lessons, then moved to
``inbox/processed`` — never deleted.

The daemon calls :func:`scan` every few minutes.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from .knowledge import TEXT_SUFFIXES, add as index_documents
from .learning import digest
from .skills import learn

INBOX = "knowledge/inbox"
PROCESSED = "knowledge/inbox/processed"


def inbox_dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / INBOX


def processed_dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / PROCESSED


def ensure(runtime_dir: str | Path) -> Path:
    """Create the inbox and a short note explaining how to use it."""

    runtime = Path(runtime_dir)
    folder = inbox_dir(runtime)
    folder.mkdir(parents=True, exist_ok=True)
    note = folder / "BURAYA-BELGE-BIRAK.txt"
    if not note.exists():
        note.write_text(
            "Bu klasöre yazılım/kod ile ilgili belgelerini kopyala.\n"
            "Desteklenen türler: .md .txt .rst .py .js .json .yaml .yml\n\n"
            "Sistem her turda buradaki yeni belgeleri okur:\n"
            "  - bilgi ağına ekler (parçalar)\n"
            "  - beceri kartı çıkarır\n"
            "  - ders çıkarır (model varsa özet, yoksa başlıklardan)\n"
            "Sonra belgeyi 'processed' klasörüne taşır; silmez.\n",
            encoding="utf-8",
        )
    processed_dir(runtime).mkdir(parents=True, exist_ok=True)
    return folder


def _pending(folder: Path) -> list[Path]:
    return [
        path
        for path in sorted(folder.rglob("*"))
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not path.name.startswith("BURAYA")
        and PROCESSED.split("/")[-1] not in path.parts
    ]


def scan(runtime_dir: str | Path, *, limit: int = 20) -> dict:
    runtime = Path(runtime_dir)
    folder = ensure(runtime)
    files = _pending(folder)[:limit]
    if not files:
        return {"documents": 0, "chunks": 0, "skills": 0, "lessons": 0, "moved": 0}

    indexed = {"documents": 0, "chunks": 0}
    skills = {"cards": 0}
    lessons = {"lessons": 0}
    moved = 0
    target = processed_dir(runtime)
    for path in files:
        try:
            result = index_documents(runtime, path)
            indexed["documents"] += int(result.get("documents") or 0)
            indexed["chunks"] += int(result.get("chunks") or 0)
            skills["cards"] += int(learn(runtime, path).get("cards") or 0)
            lessons["lessons"] += int(digest(runtime, path).get("lessons") or 0)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            shutil.move(str(path), str(target / f"{stamp}-{path.name}"))
            moved += 1
        except Exception:  # noqa: BLE001 - one bad file must not stop the rest
            continue
    return {
        "documents": indexed["documents"],
        "chunks": indexed["chunks"],
        "skills": skills["cards"],
        "lessons": lessons["lessons"],
        "moved": moved,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    if "--add" in args:
        position = args.index("--add")
        source = Path(args[position + 1])
        folder = ensure(runtime)
        copied = 0
        if source.is_file():
            shutil.copy2(source, folder / source.name)
            copied = 1
        elif source.is_dir():
            for path in source.rglob("*"):
                if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                    shutil.copy2(path, folder / f"{copied:03d}-{path.name}")
                    copied += 1
        result = scan(runtime)
        print(f"kopyalandı: {copied} · işlendi: {result['moved']} · beceri: {result['skills']} · ders: {result['lessons']}")
        return 0
    if "--scan" in args:
        result = scan(runtime)
        print(
            f"alındı: {result['moved']} belge · {result['chunks']} parça · "
            f"{result['skills']} beceri · {result['lessons']} ders"
        )
        return 0
    folder = ensure(runtime)
    print(f"belge klasörü: {folder}")
    print("belgelerini buraya kopyala; sistem kendi işler.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
