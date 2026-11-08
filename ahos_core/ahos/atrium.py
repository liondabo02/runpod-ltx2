"""Agent Atrium desenleri — ön masa, rozetler ve günlük (chronicle).

Agent Atrium'un (Venutian/agent-atrium) en değerli katkısı: **seni bekleyenleri
öne çıkarmak**. Ofiste her ajanın rozeti vardır:

- `⌨` çalışıyor      (thread aktif)
- `?` seni bekliyor  (onay/soru)
- `!` hata/engel
- `✓` tamamlandı
- `·` boşta

Ve "ön masa" (front desk): seni bekleyen veya takılan ajanların listesi, en yeni
önce. Sekme başlığında sayaç olarak gösterilir.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

BADGES = {
    "working": "⌨",
    "waiting": "?",
    "error": "!",
    "done": "✓",
    "idle": "·",
}


def _rows(runtime: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    db = runtime / "company-service.db"
    if not db.exists():
        return []
    try:
        with sqlite3.connect(db) as con:
            con.row_factory = sqlite3.Row
            return list(con.execute(sql, params))
    except sqlite3.Error:
        return []


def badge_for(status: str, *, error: str = "") -> str:
    """Görev durumundan rozet üretir."""

    if status == "running":
        return BADGES["working"]
    if status == "pending":
        return BADGES["working"]
    if status == "blocked":
        low = (error or "").casefold()
        if any(word in low for word in ("onay", "izin", "approval", "soru")):
            return BADGES["waiting"]
        return BADGES["error"]
    if status == "completed":
        return BADGES["done"]
    return BADGES["idle"]


def needs_attention(runtime_dir: str | Path, *, limit: int = 20) -> list[dict]:
    """Ön masa: seni bekleyen (?) ve takılan (!) işler, en yeni önce."""

    runtime = Path(runtime_dir)
    rows = _rows(
        runtime,
        "select mission_id, objective, primary_department, status, last_error, updated_at "
        "from missions where status in ('blocked','running') order by updated_at desc limit ?",
        (limit,),
    )
    items: list[dict] = []
    for row in rows:
        badge = badge_for(row["status"], error=row["last_error"] or "")
        if badge not in {BADGES["waiting"], BADGES["error"], BADGES["working"]}:
            continue
        items.append(
            {
                "mission_id": row["mission_id"],
                "department": row["primary_department"],
                "objective": (row["objective"] or "")[:100],
                "badge": badge,
                "kind": "bekliyor" if badge == BADGES["waiting"] else ("hata" if badge == BADGES["error"] else "çalışıyor"),
                "reason": (row["last_error"] or "")[:120],
                "at": row["updated_at"],
            }
        )
    return items


def attention_counts(items: list[dict]) -> dict[str, int]:
    waiting = sum(1 for item in items if item["badge"] == BADGES["waiting"])
    errors = sum(1 for item in items if item["badge"] == BADGES["error"])
    working = sum(1 for item in items if item["badge"] == BADGES["working"])
    return {"waiting": waiting, "errors": errors, "working": working, "total": len(items)}


def title_text(counts: dict[str, int]) -> str:
    """Sekme başlığı: `(2 bekliyor · 1 hata)`."""

    parts = []
    if counts.get("waiting"):
        parts.append(f"{counts['waiting']} bekliyor")
    if counts.get("errors"):
        parts.append(f"{counts['errors']} hata")
    return f"({', '.join(parts)})" if parts else ""


# ------------------------------- chronicle -------------------------------


@dataclass(frozen=True)
class ChronicleEvent:
    at: str
    kind: str
    detail: str


def chronicle_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "chronicle.jsonl"


def record(runtime_dir: str | Path, kind: str, detail: str) -> ChronicleEvent:
    """Günlüğe olay yazar (append-only, son 500 tutulur)."""

    runtime = Path(runtime_dir)
    path = chronicle_path(runtime)
    event = ChronicleEvent(at=time.strftime("%Y-%m-%dT%H:%M:%S"), kind=kind, detail=detail[:200])
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.__dict__, ensure_ascii=False) + "\n")

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > 500:
        path.write_text("\n".join(lines[-500:]) + "\n", encoding="utf-8")
    return event


def chronicle(runtime_dir: str | Path, *, limit: int = 20) -> list[dict]:
    """Son olaylar (en yeni önce)."""

    path = chronicle_path(runtime_dir)
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events[::-1]
