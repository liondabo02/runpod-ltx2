"""Kolektif koordinasyon döngüsü: uzman indeksi, mentorluk, devir önerileri.

Yaptığı:
- cognition uzman indeksini ve mentor eşleşmelerini tazeler,
- engelli görevler için departman yeteneğine göre uzman arar,
- `_collective.jsonl` dosyasına **öneri** devri yazar (verified=false),
- `_coordination.json` özetini üretir.

Yapmadığı: görev çalıştırmaz, başarı puanı yazmaz, yetki/harcama değiştirmez.
Paylaşılan bir öneri gerçek başarı sayılmaz; önce test/QA gerekir.

Kullanım:
    python tools/collective_loop.py --once
    python tools/collective_loop.py --interval 300
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
DB = RUNTIME / "company-service.db"
COLLECTIVE = RUNTIME / "cognition" / "_collective.jsonl"
sys.path.insert(0, str(CORE))


def _departments() -> list[dict]:
    try:
        payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
        return payload.get("departments") if isinstance(payload, dict) else payload
    except (OSError, json.JSONDecodeError):
        return []


def _blocked(limit: int = 20) -> list[dict]:
    if not DB.is_file():
        return []
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
        rows = con.execute(
            "select mission_id, objective, primary_department, last_error "
            "from missions where status='blocked' order by updated_at desc limit ?",
            (limit,)).fetchall()
    return [{"mission_id": r[0], "objective": r[1], "department": r[2], "error": r[3]}
            for r in rows]


def _handoff_seen() -> set[str]:
    seen = set()
    if not COLLECTIVE.is_file():
        return seen
    for line in COLLECTIVE.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "handoff" and row.get("mission_id"):
            seen.add(str(row["mission_id"]))
    return seen


def cycle() -> dict:
    from ahos import cognitive_memory as cm

    departments = _departments()
    index = cm.expert_index(RUNTIME, departments)
    mentors = cm.mentor_pairs(RUNTIME, departments)
    by_department = {str(d.get("department_id")): d for d in departments}
    seen = _handoff_seen()
    proposals = []
    for mission in _blocked():
        if mission["mission_id"] in seen:
            continue
        dep = by_department.get(str(mission["department"])) or {}
        capabilities = []
        for step in dep.get("workers") or []:
            for cap in step.get("capabilities") or []:
                if cap not in capabilities:
                    capabilities.append(cap)
        expert = None
        for cap in capabilities:
            rows = cm.find_expert(RUNTIME, cap, limit=1)
            if rows:
                expert = {**rows[0], "skill": cap}
                break
        if expert is None:
            continue
        record = cm.handoff(
            RUNTIME, mission_id=mission["mission_id"],
            from_worker=f"{mission['department']}-manager",
            to_worker=expert["worker"],
            reason=f"engel: {str(mission.get('error') or '')[:120]} · yetenek: {expert['skill']}",
            evidence_ok=False)
        proposals.append(record)
    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "departments": len(departments),
        "skills_indexed": len(index),
        "mentor_pairs": len(mentors),
        "blocked_scanned": len(_blocked()),
        "handoffs_proposed": len(proposals),
        "note": "proposals only; verified=false; not counted as success",
    }
    (RUNTIME / "cognition" / "_coordination.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--log-file", default=str(RUNTIME / "reports" / "collective-loop.log"))
    args = parser.parse_args(argv)
    log = Path(args.log_file)
    while True:
        try:
            line = json.dumps(cycle(), ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 - döngü durmaz
            line = json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
        print(line)
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
        if args.once:
            return 0
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
