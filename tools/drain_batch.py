"""Kuyruktaki bekleyen görevleri parti halinde çalıştırır (drain).

Kullanım:
    python tools/drain_batch.py --limit 25
    python tools/drain_batch.py --limit 25 --dry-run

- company-service.db'deki en eski `pending` görevleri sırayla sahiplenir,
- owner_console + queue_drain ile aynı yürütme yolunu kullanır,
- her görev için durum/neden ve toplam süreyi yazar,
- sonucu `runtime/queue-drain-log.jsonl` dosyasına ekler.

Kural: sayı vermeden önce kaynak yazılır (AGENTS.md §5). Bu araç yalnız
gerçek veritabanı kayıtlarını raporlar; uydurma görev üretmez.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))

LOG = RUNTIME / "queue-drain-log.jsonl"


def _mission_rows(mission_ids: list[str]) -> dict[str, dict]:
    import sqlite3

    if not mission_ids:
        return {}
    db = RUNTIME / "company-service.db"
    placeholders = ",".join("?" for _ in mission_ids)
    with sqlite3.connect(db) as con:
        rows = con.execute(
            f"select mission_id, status, primary_department, objective, last_error, "
            f"updated_at from missions where mission_id in ({placeholders})",
            mission_ids,
        ).fetchall()
    return {
        str(row[0]): {
            "status": str(row[1]),
            "department": str(row[2]),
            "objective": str(row[3]),
            "error": str(row[4] or ""),
            "updated_at": str(row[5] or ""),
        }
        for row in rows
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=25, help="parti büyüklüğü")
    parser.add_argument("--owner", default="queue-drainer", help="lease sahibi")
    parser.add_argument("--dry-run", action="store_true", help="yalnız say, çalıştırma")
    args = parser.parse_args(argv)

    if args.limit < 1:
        print("limit >= 1 olmalı")
        return 2

    from ahos.owner_console import build_default_console
    from ahos.queue_drain import drain

    started = time.monotonic()
    console = build_default_console(RUNTIME)

    if args.dry_run:
        report = drain(console, owner=args.owner, limit=args.limit, dry_run=True)
        print(f"kuru çalışma: {report['skipped']} görev çalıştırılabilir")
        for mission_id in report["would_run"]:
            print(f"  {mission_id}")
        return 0

    report = drain(console, owner=args.owner, limit=args.limit)
    elapsed = round(time.monotonic() - started, 1)

    executed = list(report.get("executed") or [])
    blocked_ids = list(report.get("blocked") or [])
    rows = _mission_rows(executed)
    statuses: dict[str, int] = {}
    for row in rows.values():
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1

    print(f"parti: {len(executed)} görev yürütüldü, {len(blocked_ids)} departman yok diye engellendi, {elapsed}s")
    for mission_id in executed:
        row = rows.get(mission_id, {})
        status = row.get("status", "?")
        reason = (row.get("error") or "").replace("\n", " ")[:120]
        print(f"  {mission_id[:52]:52} {status:10} {reason}")

    entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "limit": args.limit,
        "executed": len(executed),
        "blocked": len(blocked_ids),
        "seconds": elapsed,
        "by_status": statuses,
        "missions": [
            {
                "mission_id": mission_id,
                "status": rows.get(mission_id, {}).get("status"),
                "department": rows.get(mission_id, {}).get("department"),
                "error": (rows.get(mission_id, {}).get("error") or "")[:300],
            }
            for mission_id in executed
        ],
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"günlük: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
