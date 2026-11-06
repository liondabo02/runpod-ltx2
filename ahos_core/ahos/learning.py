"""Learning from documents: turn the owner's library into reusable lessons.

The owner downloads software documents. ``digest`` reads them and extracts short,
reusable engineering lessons, which are stored append-only and injected into
worker prompts. With a model it writes real summaries; offline it derives lessons
from headings and opening sentences, so learning never stops.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

from .knowledge import TEXT_SUFFIXES, add as index_documents

LESSONS_PATH = "knowledge/lessons.jsonl"
MAX_DOCS_PER_RUN = 6


def _lessons_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / LESSONS_PATH


def _known(runtime_dir: str | Path) -> set[str]:
    path = _lessons_path(runtime_dir)
    seen: set[str] = set()
    if not path.is_file():
        return seen
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            seen.add(str(json.loads(line).get("doc_id") or ""))
        except json.JSONDecodeError:
            continue
    return seen


def _offline_lessons(text: str, name: str) -> list[str]:
    """Deterministic: section headings and their first sentence."""

    lessons: list[str] = []
    blocks = re.split(r"\n(?=#{1,3}\s)", text)
    for block in blocks:
        heading = re.match(r"#{1,3}\s+(.+)", block.strip())
        if not heading:
            continue
        title = heading.group(1).strip()[:80]
        body = block.strip().splitlines()[1:]
        sentence = " ".join(line.strip() for line in body if line.strip())[:220]
        if sentence:
            lessons.append(f"{name} · {title}: {sentence}")
        if len(lessons) >= 5:
            break
    return lessons


def _model_lessons(text: str, name: str, settings) -> list[str]:
    from .llm_executor import http_transport

    prompt = (
        f"Belge: {name}\n\n{text[:5000]}\n\n"
        "Bu belgeden yazılım geliştirmede tekrar kullanılabilecek en fazla 4 ders çıkar. "
        "Her ders tek cümle, somut ve uygulanabilir olsun. Satır başına bir ders yaz, "
        "başka açıklama ekleme."
    )
    answer = http_transport(
        "Yazılım mimarisi eğitmenisin; kısa ve uygulanabilir dersler çıkarırsın.",
        prompt,
        settings,
    )
    return [
        line.strip(" -*\t")[:220]
        for line in answer.splitlines()
        if line.strip() and len(line.strip()) > 20
    ][:4]


def digest(runtime_dir: str | Path, source: str | Path, *, limit: int = MAX_DOCS_PER_RUN) -> dict:
    runtime = Path(runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    target = Path(source)
    files = [target] if target.is_file() else [
        path for path in sorted(target.rglob("*"))
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    ]
    index_result = index_documents(runtime, target)
    seen = _known(runtime)

    settings = None
    try:
        from .llm_executor import load_settings

        settings = load_settings()
    except Exception:  # noqa: BLE001 - offline is fine
        settings = None

    path = _lessons_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    mode = "model" if settings is not None else "offline"
    with path.open("a", encoding="utf-8") as handle:
        for candidate in files[:limit]:
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.strip():
                continue
            doc_id = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
            if doc_id in seen:
                continue
            seen.add(doc_id)
            lessons: list[str] = []
            if settings is not None:
                try:
                    lessons = _model_lessons(text, candidate.name, settings)
                except Exception:  # noqa: BLE001 - fall back to offline extraction
                    lessons = []
            if not lessons:
                lessons = _offline_lessons(text, candidate.name)
                mode = "offline" if settings is None else "model+offline"
            for lesson in lessons:
                handle.write(
                    json.dumps(
                        {
                            "doc_id": doc_id,
                            "name": candidate.name,
                            "path": str(candidate),
                            "lesson": lesson,
                            "mode": mode,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1
    return {
        "indexed": index_result,
        "lessons": written,
        "mode": mode,
        "total": len(_known(runtime)),
    }


def lessons(runtime_dir: str | Path, limit: int = 5) -> list[dict]:
    path = _lessons_path(runtime_dir)
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


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
        result = digest(runtime, Path(args[position + 1]))
        print(
            f"öğrenildi: {result['lessons']} ders · {result['mode']} · "
            f"toplam {result['total']} belge işlendi"
        )
        return 0
    for row in lessons(runtime, limit=10):
        print(f"- {row['lesson']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
