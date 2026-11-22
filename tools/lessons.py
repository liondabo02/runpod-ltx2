"""AHOS Ders Hafızası: işçilerin sürekli öğrenmesi (diziden bağımsız).

Dersler studio/agents/memory/<işçi>.jsonl dosyasında tutulur. Her ders: kaynak (owner/auto/qa), sayaç, zaman.
Promptlara kısa bir 'öğrenilmiş dersler' bloğu olarak eklenir. Güvenlik: yalnız METİN öğüdüdür; kod/onay değiştirmez,
silinebilir (retire), sayısı sınırlıdır, sahibin dersleri önceliklidir.
"""
import datetime, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
MEM = os.environ.get("AHOS_MEMORY_DIR") or os.path.join(ROOT, "studio", "agents", "memory")
ALIASES = {"writer": ["writers_room", "director"], "critic": ["writers_room_critic"]}
MAX_PER_WORKER = 40


def _path(worker):
    return os.path.join(MEM, worker + ".jsonl")


def _norm(t):
    return re.sub(r"\W+", " ", str(t).lower()).strip()


def load(worker):
    p = _path(worker)
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("lesson"):
            r.setdefault("source", "auto"); r.setdefault("count", 1)
            out.append(r)
    return out


def _save(worker, rows):
    os.makedirs(MEM, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r.get("source") == "owner", r.get("count", 1), r.get("at", "")), reverse=True)[:MAX_PER_WORKER]
    with open(_path(worker), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def add(worker, lesson, source="auto", count=1):
    rows = load(worker)
    key = _norm(lesson)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for r in rows:
        if _norm(r["lesson"]) == key:
            r["count"] = r.get("count", 1) + count; r["at"] = now
            if source == "owner":
                r["source"] = "owner"
            _save(worker, rows); return r
    r = {"status": "LESSON", "worker": worker, "lesson": str(lesson).strip(), "source": source, "count": count, "at": now}
    rows.append(r); _save(worker, rows)
    return r


def retire(worker, substring):
    rows = load(worker)
    keep = [r for r in rows if substring.lower() not in r["lesson"].lower()]
    _save(worker, keep)
    return len(rows) - len(keep)


def top(worker, n=8):
    names = ALIASES.get(worker, []) + [worker]
    rows = []
    for w in names:
        rows += load(w)
    rows.sort(key=lambda r: (r.get("source") == "owner", r.get("count", 1), r.get("at", "")), reverse=True)
    seen, out = set(), []
    for r in rows:
        k = _norm(r["lesson"])
        if k not in seen:
            seen.add(k); out.append(r)
    return out[:n]


def prompt_block(worker, n=8):
    rows = top(worker, n)
    if not rows:
        return ""
    lines = ["- " + ("[SAHİBİN TALİMATI] " if r.get("source") == "owner" else "") + r["lesson"] for r in rows]
    return "\n\nGEÇMİŞTEN ÖĞRENİLMİŞ DERSLER (bunlara uy, aynı hatayı tekrarlama):\n" + "\n".join(lines)
