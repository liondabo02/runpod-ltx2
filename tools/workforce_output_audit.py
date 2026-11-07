"""İşçi → görev → çıktı → bağımsız QA → kayıt zincirini denetler (salt okunur).

Yalnız `delivery.verified=1` olan görevler "ürün" sayılır; düşünce/öneri/mesaj
kayıtları ürün sayılmaz. Rapor: hangi işçi gerçekten doğrulanmış çıktı üretmiş,
hangi departman kapsanmış, kaç işçi henüz kanıtsız.

Kullanım:
    python tools/workforce_output_audit.py --runtime <live runtime> --out <json>
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def audit(runtime: Path) -> dict:
    db = runtime / "company-service.db"
    workers: dict[str, dict] = defaultdict(lambda: {"verified": 0, "qa": 0, "last": ""})
    departments: dict[str, dict] = defaultdict(lambda: {"completed": 0, "verified": 0})
    verified_total = 0
    parsed = 0
    if db.is_file():
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for row in con.execute(
                "select primary_department, status, result_json, updated_at from missions "
                "where status='completed'"):
            department = str(row["primary_department"] or "")
            departments[department]["completed"] += 1
            payload = _loads(row["result_json"])
            if not payload:
                continue
            parsed += 1
            delivery = payload.get("delivery") or {}
            if not delivery.get("verified"):
                continue
            verified_total += 1
            departments[department]["verified"] += 1
            stamp = str(row["updated_at"] or "")
            seen = set()
            for step in payload.get("steps") or []:
                worker = str(step.get("worker_id") or "")
                qa = str(step.get("qa_worker_id") or "")
                if worker and worker not in seen:
                    seen.add(worker)
                    workers[worker]["verified"] += 1
                    workers[worker]["last"] = max(workers[worker]["last"], stamp)
                if qa:
                    workers[qa]["qa"] += 1
                    workers[qa]["last"] = max(workers[qa]["last"], stamp)
        con.close()

    roster_path = runtime / "departments.json"
    roster: list[str] = []
    if roster_path.is_file():
        try:
            payload = json.loads(roster_path.read_text(encoding="utf-8"))
            for department in payload.get("departments") or []:
                for worker in department.get("workers") or []:
                    if worker.get("worker_id"):
                        roster.append(str(worker["worker_id"]))
        except (OSError, json.JSONDecodeError):
            roster = []

    proven = sorted(name for name, item in workers.items() if item["verified"] > 0)
    unproven = sorted(set(roster) - set(proven))
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runtime": str(runtime),
        "completed_total": sum(item["completed"] for item in departments.values()),
        "completed_with_result": parsed,
        "verified_deliveries": verified_total,
        "roster_workers": len(roster),
        "workers_with_verified_output": len(proven),
        "workers_without_verified_output": len(unproven),
        "unproven_sample": unproven[:10],
        "departments": {name: dict(item) for name, item in sorted(departments.items())},
        "top_workers": sorted(
            ({"worker_id": name, **item} for name, item in workers.items() if item["verified"]),
            key=lambda item: (-item["verified"], item["worker_id"]))[:10],
        "note": "Yalnız delivery.verified=1 ürün sayıldı; düşünce/mesaj/öneri sayılmadı.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default=str(Path("ahos_core") / "runtime"))
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    report = audit(Path(args.runtime))
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "completed_total", "completed_with_result", "verified_deliveries",
        "roster_workers", "workers_with_verified_output",
        "workers_without_verified_output", "unproven_sample")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
