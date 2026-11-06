"""Görev tamamlandıkça bilişsel profili güncelleyen artımlı senkron döngüsü.

`cognition_init.py` toplu kurulum yapar; bu araç ise her yeni doğrulanmış
görevi (mission_id bazında tekilleştirerek) ilgili işçilerin profiline yazar:
episodic → procedural → reflection → semantic → metacognition → emotion.

Kuyruk dolu olsa da çalışır (öğrenme görev yürütücüsünü engellemez), çünkü
yalnız SQLite okur ve küçük JSON dosyalarına yazar.

Kullanım:
    python tools/cognition_sync.py --once
    python tools/cognition_sync.py --interval 60
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
STATE = RUNTIME / "cognition" / ".sync-state.json"
sys.path.insert(0, str(CORE))


def _departments() -> list[dict]:
    try:
        payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
        return payload.get("departments") if isinstance(payload, dict) else payload
    except (OSError, json.JSONDecodeError):
        return []


def _route(objective: str) -> str:
    import re

    text = (objective or "").strip()
    if text.startswith("render:"):
        return "render"
    if re.search(r"dosyas[ıi]n[ıi]n sonuna|sonuna .*(ekle|yorum|satır)", text, re.I):
        return "simple_edit"
    from ahos.scope import should_document

    return "document" if should_document(text) else "executor"


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last_updated_at": ""}


def _save_state(payload: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_name(STATE.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE)


def sync_once(*, limit: int = 300, update_index: bool = False) -> dict:
    from ahos import cognitive_memory as cm

    state = _state()
    since = str(state.get("last_updated_at") or "")
    if not DB.is_file():
        return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "error": "db_missing"}
    with sqlite3.connect(DB) as con:
        if since:
            rows = con.execute(
                "select mission_id, objective, status, result_json, last_error, updated_at "
                "from missions where result_json is not null and updated_at > ? "
                "order by updated_at asc limit ?", (since, limit)).fetchall()
        else:
            rows = con.execute(
                "select mission_id, objective, status, result_json, last_error, updated_at "
                "from missions where result_json is not null order by updated_at desc limit ?",
                (limit,)).fetchall()
            rows = list(reversed(rows))
        pending = con.execute("select count(*) from missions where status='pending'").fetchone()[0]

    departments = _departments()
    department_of = {str(w.get("worker_id")): str(d.get("department_id") or "")
                     for d in departments for w in d.get("workers") or []}
    written = {"missions": 0, "profiles": 0, "episodes": 0, "semantic": 0, "skipped_no_evidence": 0}
    touched: set[str] = set()
    last_stamp = since

    for mission_id, objective, status, raw, error, updated_at in rows:
        last_stamp = max(last_stamp, str(updated_at or ""))
        try:
            result = json.loads(raw)
        except (TypeError, ValueError):
            continue
        steps = result.get("steps") or []
        delivery = result.get("delivery") or {}
        qa_evidence = bool(delivery.get("verified")) or any(
            step.get("qa_worker_id") for step in steps)
        if not qa_evidence:
            written["skipped_no_evidence"] += 1
            continue
        plan_type = _route(str(objective or ""))
        ok = str(status) == "completed"
        wrote_for_mission = False
        for step in steps:
            worker = str(step.get("worker_id") or "")
            if not worker:
                continue
            department = department_of.get(worker, str(step.get("department") or ""))
            try:
                profile = cm.load(RUNTIME, worker, department)
            except ValueError:
                continue
            known = {row.get("mission_id") for row in profile["memory"]["episodic"]}
            if str(mission_id) in known:
                continue
            cm.record_episode(profile, mission_id=mission_id, outcome=str(status),
                              summary=str(objective or ""), evidence_ok=True,
                              plan_type=plan_type)
            cm.learn_procedural(profile, plan_type=plan_type, ok=ok)
            cm.reflect(profile, mission_id=mission_id, ok=ok, reason=str(error or ""),
                       plan_type=plan_type, evidence_ok=True)
            cm.remember_long_term(profile, mission_id=str(mission_id),
                                  plan_type=plan_type, ok=ok, department=department)
            cm.meta_note(profile, "mission_qa", ok)
            if ok:
                cm.learn_semantic(
                    profile,
                    statement=f"{plan_type} yolu {mission_id} görevinde bağımsız QA ile doğrulandı",
                    source=f"mission:{mission_id}", mission_id=str(mission_id), verified=True)
                cm.share_from_profile(
                    RUNTIME, profile,
                    statement=f"{department} · {plan_type} yolu bağımsız QA ile doğrulandı",
                    source=f"mission:{mission_id}", mission_id=str(mission_id),
                    verified=True)
                written["semantic"] += 1
            cm.metacognition(profile)
            cm.emotion(profile, pending=int(pending or 0), idle=int(pending or 0) == 0,
                       last_outcome="completed" if ok else "blocked")
            cm.save(RUNTIME, profile)
            written["episodes"] += 1
            touched.add(worker)
            wrote_for_mission = True
        if wrote_for_mission:
            written["missions"] += 1

    written["profiles"] = len(touched)
    if update_index and touched:
        cm.expert_index(RUNTIME, departments)
        cm.mentor_pairs(RUNTIME, departments)
    _save_state({"last_updated_at": last_stamp,
                 "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "pending": int(pending or 0)})
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "since": since,
            "last_updated_at": last_stamp, "pending": int(pending or 0), **written}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--index-every", type=int, default=10)
    parser.add_argument("--log-file", default=str(RUNTIME / "reports" / "cognition-sync.log"))
    args = parser.parse_args(argv)
    log = Path(args.log_file)
    cycle = 0
    while True:
        try:
            summary = sync_once(update_index=(cycle % max(1, args.index_every) == 0))
            line = json.dumps(summary, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 - servis döngüsü durmaz
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
        cycle += 1
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
