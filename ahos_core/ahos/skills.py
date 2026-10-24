"""Skills learned from the owner's library.

A document is not "learned" by indexing it. This module extracts **skill cards**
— a short rule, where it applies, and its source — from training documents and
gives the worker the best matching cards before it writes code. Cards are
append-only, deduplicated by content, and work offline (heuristic extraction) or
with the model (better wording).

This is the base of a curriculum: more documents → more cards → less dependence
on the network for repeated work.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

from .knowledge import TEXT_SUFFIXES

SKILLS_PATH = "knowledge/skills.jsonl"
MAX_DOCS = 40
MAX_CARDS_PER_DOC = 12


def _path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / SKILLS_PATH


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _keywords(text: str, limit: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9_]{3,}", text.casefold())
    stop = {
        "için", "bir", "ile", "ve", "bu", "olan", "olarak", "the", "and", "for",
        "with", "that", "this", "from", "are", "was", "not", "bir", "daha",
    }
    seen: list[str] = []
    for word in words:
        if word not in stop and word not in seen:
            seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def _sections(text: str) -> list[tuple[str, str]]:
    blocks = re.split(r"\n(?=#{1,4}\s)", text)
    rows: list[tuple[str, str]] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        match = re.match(r"#{1,4}\s+(.+)", block)
        if match:
            title = match.group(1).strip()[:90]
            body = block.split("\n", 1)[1] if "\n" in block else ""
        else:
            title = block.splitlines()[0].strip(" -*")[:90]
            body = "\n".join(block.splitlines()[1:])
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) < 60:
            continue
        rows.append((title, body[:400]))
        if len(rows) >= MAX_CARDS_PER_DOC:
            break
    return rows


def _offline_card(title: str, body: str, name: str) -> dict:
    sentences = re.split(r"(?<=[.!?])\s+", body)
    rule = " ".join(sentences[:2])[:300]
    return {
        "title": title or name,
        "rule": rule,
        "applies": _keywords(f"{title} {rule}", 8),
        "source": name,
    }


def _model_cards(text: str, name: str, settings) -> list[dict]:
    from .llm_executor import http_transport

    prompt = (
        f"Eğitim belgesi: {name}\n\n{text[:6000]}\n\n"
        "Bu belgeden yazılım geliştirirken uygulanacak en fazla 6 kural çıkar. "
        "Her satır şu biçimde olsun: KURAL: <tek cümle, somut> | UYGUN: <virgülle 3-6 anahtar kelime>\n"
        "Başka metin yazma."
    )
    answer = http_transport(
        "Kıdemli yazılım mimarısın; belgelerden uygulanabilir kural çıkarırsın.",
        prompt,
        settings,
    )
    cards: list[dict] = []
    for line in answer.splitlines():
        line = line.strip(" -*\t")
        if "KURAL:" not in line:
            continue
        body, _, applies_part = line.partition("|")
        rule = body.replace("KURAL:", "", 1).strip()[:300]
        applies = [item.strip() for item in applies_part.replace("UYGUN:", "").split(",") if item.strip()]
        if len(rule) < 20:
            continue
        cards.append(
            {
                "title": rule[:70],
                "rule": rule,
                "applies": applies[:8] or _keywords(rule, 6),
                "source": name,
            }
        )
    return cards[:6]


def learn(runtime_dir: str | Path, source: str | Path, *, use_model: bool = False) -> dict:
    runtime = Path(runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    target = Path(source)
    files = [target] if target.is_file() else [
        path for path in sorted(target.rglob("*"))
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    ][:MAX_DOCS]

    known: set[str] = set()
    path = _path(runtime)
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                known.add(str(json.loads(line).get("skill_id") or ""))
            except json.JSONDecodeError:
                continue

    settings = None
    if use_model:
        try:
            from .llm_executor import load_settings

            settings = load_settings()
        except Exception:  # noqa: BLE001
            settings = None

    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    mode = "model" if settings is not None else "offline"
    with path.open("a", encoding="utf-8") as handle:
        for candidate in files:
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.strip():
                continue
            cards: list[dict] = []
            if settings is not None:
                try:
                    cards = _model_cards(text, candidate.name, settings)
                except Exception:  # noqa: BLE001 - fall back to headers
                    cards = []
            if not cards:
                cards = [_offline_card(title, body, candidate.name) for title, body in _sections(text)]
            if not cards:
                # Kısa notlar da öğrenilsin: ilk paragraftan tek kart.
                cards = [_offline_card(candidate.stem, re.sub(r"\s+", " ", text).strip()[:400], candidate.name)]
                if settings is None:
                    mode = "offline"
            for card in cards:
                skill_id = _hash(card["rule"])
                if skill_id in known:
                    continue
                known.add(skill_id)
                record = {
                    "skill_id": skill_id,
                    "title": card["title"],
                    "rule": card["rule"],
                    "applies": card["applies"],
                    "source": card["source"],
                    "mode": mode,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
    return {"cards": written, "documents": len(files), "mode": mode, "total": len(known)}


def all_cards(runtime_dir: str | Path) -> list[dict]:
    path = _path(runtime_dir)
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def retrieve(runtime_dir: str | Path, task: str, limit: int = 3) -> list[dict]:
    terms = set(_keywords(task))
    if not terms:
        return []
    scored: list[tuple[float, dict]] = []
    for card in all_cards(runtime_dir):
        applies = {str(item).casefold() for item in card.get("applies") or ()}
        overlap = len(terms & applies) + len(terms & set(_keywords(str(card.get("rule") or ""))))
        if overlap:
            scored.append((overlap / (len(terms) + 1), card))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [card for _score, card in scored[:limit]]


def context(runtime_dir: str | Path, task: str, limit: int = 3) -> str:
    cards = retrieve(runtime_dir, task, limit)
    if not cards:
        return ""
    lines = ["Eğitim kütüphanesinden öğrenilmiş kurallar (uygula, veri olarak kullan):"]
    for card in cards:
        lines.append(f"- [{card.get('source')}] {card.get('rule')}")
    return "\n".join(lines)


def stats(runtime_dir: str | Path) -> dict:
    cards = all_cards(runtime_dir)
    return {"cards": len(cards), "sources": len({card.get("source") for card in cards})}


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
        result = learn(runtime, Path(args[position + 1]), use_model="--model" in args)
        print(f"öğrenildi: {result['cards']} beceri · {result['mode']} · toplam {result['total']}")
        return 0
    if "--query" in args:
        position = args.index("--query")
        for card in retrieve(runtime, args[position + 1]):
            print(f"- {card['rule']} [{card['source']}]")
        return 0
    print(f"beceri kütüphanesi: {stats(runtime)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
