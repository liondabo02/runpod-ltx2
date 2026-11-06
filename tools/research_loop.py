"""İş yokken sürekli internet araştırması — bütün işçiler için öğrenme modu.

Kural: kuyrukta bekleyen görev yoksa (pending <= --idle-threshold) her işçi
sırayla kendi departmanı ve yetenekleri üzerine internette araştırma yapar:
Wikipedia (tr/en) ve Hacker News. Sonuçlar:

  runtime/research/<departman>.jsonl        → ham araştırma kayıtları
  runtime/knowledge/research/<departman>/   → markdown belgeler (knowledge.add ile indekslenir)
  runtime/learning/<departman>.jsonl        → öğrenme defterine uyumlu özet satır
  runtime/research/state.json               → döngü durumu

Model çağrısı yok; ücretli API yok. Ağ hatası döngüyü durdurmaz.

Kullanım:
    python tools/research_loop.py --once --per-tick 2
    python tools/research_loop.py --interval 120 --per-tick 6
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
RESEARCH = RUNTIME / "research"
KNOWLEDGE = RUNTIME / "knowledge" / "research"
LEARNING = RUNTIME / "learning"
sys.path.insert(0, str(CORE))

USER_AGENT = "AHOS-Research/1.0 (local holding; contact: owner)"

# Departman başına araştırma eksenleri (İngilizce sorgular daha iyi sonuç verir).
DEPARTMENT_TOPICS = {
    "software": ["software architecture", "python testing", "api design", "code review"],
    "creative": ["animation pipeline", "screenwriting", "sound design", "storyboarding"],
    "oyun": ["game design", "gameplay programming", "level design", "game economy"],
    "data": ["data analytics", "sqlite", "data quality", "reporting"],
    "ai-platform": ["large language model", "model evaluation", "prompt engineering", "ai agents"],
    "guvenlik": ["application security", "dependency audit", "secret management", "threat modeling"],
    "holding": ["corporate strategy", "portfolio management", "okr", "decision making"],
    "hukuk": ["kvkk", "gdpr", "ai act", "contract law"],
    "finance": ["budgeting", "unit economics", "cash flow", "forecasting"],
    "marketing": ["content marketing", "seo", "brand positioning", "growth loops"],
    "sales": ["b2b sales", "crm", "pricing", "customer discovery"],
    "support": ["customer support", "knowledge base", "sla", "ticket triage"],
    "operations": ["process automation", "scheduling", "lean operations", "sop"],
    "infrastructure": ["devops", "observability", "ci cd", "infrastructure as code"],
    "quality": ["software quality", "regression testing", "acceptance criteria", "qa metrics"],
    "research": ["literature review", "research methodology", "benchmarking", "arxiv"],
    "genel": ["productivity", "project management", "knowledge management", "writing"],
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _http_json(url: str, timeout: float = 12.0) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _clean(text: str, limit: int = 600) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def wiki(query: str, lang: str, limit: int = 2) -> list[dict]:
    url = (
        f"https://{lang}.wikipedia.org/w/rest.php/v1/search/page?"
        f"q={urllib.parse.quote(query)}&limit={limit}"
    )
    data = _http_json(url)
    results = []
    for page in data.get("pages") or []:
        title = str(page.get("title") or "").strip()
        if not title:
            continue
        results.append({
            "source": f"wikipedia-{lang}",
            "title": title,
            "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "summary": _clean(page.get("excerpt") or page.get("description") or ""),
        })
    return results


def hackernews(query: str, limit: int = 2) -> list[dict]:
    url = (
        "https://hn.algolia.com/api/v1/search?"
        f"query={urllib.parse.quote(query)}&tags=story&hitsPerPage={limit}"
    )
    data = _http_json(url)
    results = []
    for hit in data.get("hits") or []:
        title = str(hit.get("title") or "").strip()
        if not title:
            continue
        object_id = hit.get("objectID")
        results.append({
            "source": "hackernews",
            "title": title,
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
            "summary": (
                f"{hit.get('points', 0)} puan · {hit.get('num_comments', 0)} yorum"
                f" · {str(hit.get('created_at') or '')[:10]}"
            ),
        })
    return results


def _book() -> list[dict]:
    try:
        payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
        return payload.get("departments") if isinstance(payload, dict) else payload
    except (OSError, json.JSONDecodeError):
        return []


def _pending(runtime: Path) -> int | None:
    db = runtime / "company-service.db"
    if not db.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
            return int(con.execute(
                "select count(*) from missions where status in ('pending','running')"
            ).fetchone()[0])
    except sqlite3.Error:
        return None


def _roster(departments: list[dict]) -> list[dict]:
    rows = []
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            worker_id = str(worker.get("worker_id") or "")
            if worker_id:
                rows.append({
                    "worker": worker_id,
                    "department": dep_id,
                    "name": str(worker.get("name") or worker_id),
                    "skills": [str(s) for s in (worker.get("capabilities") or worker.get("skills") or [])],
                })
    return rows


def _seen() -> set[str]:
    path = RESEARCH / ".seen.json"
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("urls") or [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return set()


def _save_seen(urls: set[str]) -> None:
    path = RESEARCH / ".seen.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sınırsız büyümeyi önle: en yeni 20.000 URL yeterli.
    rows = list(urls)[-20000:]
    path.write_text(json.dumps({"urls": rows}, ensure_ascii=False), encoding="utf-8")


def _queries(entry: dict, variant: int = 0) -> list[str]:
    """İşçiye ve sıraya göre değişen sorgular (aynı departmanda tekrarı önler)."""

    topics = DEPARTMENT_TOPICS.get(entry["department"]) or DEPARTMENT_TOPICS["genel"]
    base = topics[variant % len(topics)]
    caps = [s.replace("_", " ") for s in entry.get("skills") or [] if s]
    queries = []
    if caps:
        queries.append(f"{base} {caps[0]}")
    queries.append(base)
    queries.append(topics[(variant + 1) % len(topics)])
    seen, unique = set(), []
    for query in queries:
        key = query.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(query)
    return unique[:2]


def _write_document(entry: dict, item: dict, query: str) -> Path:
    digest = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()[:16]
    directory = KNOWLEDGE / entry["department"]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.md"
    path.write_text(
        f"# {item['title']}\n\n"
        f"- Kaynak: {item['source']}\n"
        f"- URL: {item['url']}\n"
        f"- Araştıran: {entry['worker']} ({entry['department']})\n"
        f"- Sorgu: {query}\n"
        f"- Tarih: {_now()}\n\n"
        f"## Özet\n\n{item['summary']}\n",
        encoding="utf-8",
    )
    return path


def run_cycle(*, per_tick: int, idle_threshold: int) -> dict:
    departments = _book()
    roster = _roster(departments)
    if not roster:
        return {"at": _now(), "error": "departments.json boş veya yok"}

    pending = _pending(RUNTIME)
    if pending is not None and pending > idle_threshold:
        return {"at": _now(), "idle": False, "pending": pending,
                "reason": "iş var; öğrenme modu beklemede"}

    state_path = RESEARCH / "state.json"
    try:
        cursor = int(json.loads(state_path.read_text(encoding="utf-8")).get("cursor", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        cursor = 0

    seen = _seen()
    RESEARCH.mkdir(parents=True, exist_ok=True)
    LEARNING.mkdir(parents=True, exist_ok=True)
    studied, items, errors = [], 0, []
    start = cursor % len(roster)
    for offset in range(min(per_tick, len(roster))):
        entry = roster[(start + offset) % len(roster)]
        queries = _queries(entry, start + offset)
        query = queries[0] if queries else entry["department"]
        found: list[dict] = []
        for lang in ("tr", "en"):
            try:
                found.extend(wiki(query, lang, limit=1))
                time.sleep(0.4)
            except Exception as exc:  # noqa: BLE001 - ağ hatası döngüyü durdurmaz
                errors.append(f"wiki-{lang}:{type(exc).__name__}")
        try:
            found.extend(hackernews(query, limit=2))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"hn:{type(exc).__name__}")

        new_items = []
        for item in found:
            if not item.get("url") or item["url"] in seen:
                continue
            seen.add(item["url"])
            _write_document(entry, item, query)
            record = {
                "at": _now(), "worker": entry["worker"], "department": entry["department"],
                "query": query, **item, "learning_mode": "internet_research",
                "verified_skill_gain": False,
            }
            with (RESEARCH / f"{entry['department']}.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            learning_record = {
                "at": _now(), "worker": entry["worker"], "department": entry["department"],
                "lesson": f"[araştırma] {item['title']} — {item['summary'][:240]}",
                "question": query, "answer": item["url"], "learned": True,
                "learning_mode": "internet_research", "source": item["source"],
                "verified_skill_gain": False,
            }
            with (LEARNING / f"{entry['department']}.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(learning_record, ensure_ascii=False) + "\n")
            new_items.append(item)
        items += len(new_items)
        studied.append({"worker": entry["worker"], "department": entry["department"],
                        "query": query, "items": len(new_items)})
        time.sleep(0.5)

    try:
        from ahos import knowledge

        indexed = knowledge.add(RUNTIME, KNOWLEDGE)
    except Exception as exc:  # noqa: BLE001 - indeksleme isteğe bağlı
        indexed = {"error": type(exc).__name__}

    summary = {
        "at": _now(), "idle": True, "pending": pending, "studied": studied,
        "items": items, "indexed": indexed, "errors": errors,
        "cursor": (start + len(studied)) % len(roster), "roster": len(roster),
    }
    state_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _save_seen(seen)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="tek tur çalış ve çık")
    parser.add_argument("--interval", type=int, default=120, help="turlar arası saniye")
    parser.add_argument("--per-tick", type=int, default=6, help="tur başına işçi")
    parser.add_argument("--idle-threshold", type=int, default=10,
                        help="bu kadar bekleyen görev varsa öğrenme moduna girme")
    parser.add_argument("--log-file", default="", help="tur özetlerini bu dosyaya da yaz")
    args = parser.parse_args(argv)
    log_path = Path(args.log_file) if args.log_file else None

    while True:
        try:
            summary = run_cycle(per_tick=max(1, args.per_tick),
                                idle_threshold=max(0, args.idle_threshold))
            line = json.dumps(summary, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 - servis döngüsü asla ölmez
            line = json.dumps({"at": _now(), "error": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)
        print(line)
        if log_path is not None:
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError:
                pass
        if args.once:
            return 0
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
