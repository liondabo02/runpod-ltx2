"""81 işçinin kalıcı bilişsel profilini gerçek görev kayıtlarından kurar.

Kaynak: runtime/company-service.db (missions.result_json.steps) + departments.json.
Kural: yalnız gerçekten yürütülmüş adımlar ve `delivery.verified` kanıtı yazılır;
kanıt yoksa profil `no_verified_evidence` olarak kalır. Mevcut profil ezilmez,
yalnız yeni gözlemler eklenir (mission_id ile tekilleştirilir).

Kullanım:
    python tools/cognition_init.py            # kuru: ne yazılacağını say
    python tools/cognition_init.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))

_EDIT = re.compile(r"dosyas[ıi]n[ıi]n sonuna|sonuna .*(ekle|yorum|satır)|başına .*(ekle|yorum)", re.I)


def route(objective: str) -> str:
    text = (objective or "").strip()
    if text.startswith("render:"):
        return "render"
    if _EDIT.search(text):
        return "simple_edit"
    from ahos.scope import should_document

    return "document" if should_document(text) else "executor"


def _departments() -> list[dict]:
    payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
    return payload.get("departments") if isinstance(payload, dict) else payload


def _missions() -> list[dict]:
    db = RUNTIME / "company-service.db"
    with sqlite3.connect(db) as con:
        rows = con.execute(
            "select mission_id, objective, status, result_json, last_error, updated_at "
            "from missions where result_json is not null order by updated_at asc"
        ).fetchall()
    out = []
    for mission_id, objective, status, raw, error, updated_at in rows:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        delivery = payload.get("delivery") or {}
        out.append({
            "mission_id": str(mission_id), "objective": str(objective),
            "status": str(status), "steps": payload.get("steps") or [],
            "verified": bool(delivery.get("verified")),
            "error": str(error or ""), "at": str(updated_at or ""),
        })
    return out


def sync(*, apply: bool) -> dict:
    from ahos import cognitive_memory as cm

    departments = _departments()
    missions = _missions()
    roster = [(str(d.get("department_id")), str(w.get("worker_id")))
              for d in departments for w in d.get("workers") or [] if w.get("worker_id")]
    participation: dict[str, dict[str, dict]] = {}
    for mission in missions:
        for step in mission["steps"]:
            worker = step.get("worker_id")
            if worker:  # her adım işçisi gerçek katılımcıdır
                participation.setdefault(str(worker), {})[mission["mission_id"]] = mission

    written = {"episodes": 0, "procedural": 0, "semantic": 0, "profiles": 0}
    for department, worker in roster:
        try:
            profile = cm.load(RUNTIME, worker, department)
        except ValueError:
            continue
        known = {row.get("mission_id") for row in profile["memory"]["episodic"]}
        seen_types = set()
        for mission in participation.get(worker, {}).values():
            if mission["mission_id"] in known:
                continue
            # Bağımsız QA kaydı olan her görev kanıttır: başarı ise "completed",
            # QA reddettiyse "blocked" olarak yazılır; kanıtsız görev atlanır.
            qa_evidence = any(step.get("qa_worker_id") for step in mission["steps"])
            if not (mission["verified"] or qa_evidence):
                continue
            plan_type = route(mission["objective"])
            ok = mission["status"] == "completed"
            cm.record_episode(profile, mission_id=mission["mission_id"],
                              outcome=mission["status"], summary=mission["objective"],
                              evidence_ok=True, plan_type=plan_type)
            cm.learn_procedural(profile, plan_type=plan_type, ok=ok)
            cm.reflect(profile, mission_id=mission["mission_id"], ok=ok,
                       reason=mission["error"], plan_type=plan_type, evidence_ok=True)
            if ok and plan_type not in seen_types:
                cm.learn_semantic(
                    profile,
                    statement=f"{plan_type} yolu {mission['mission_id']} görevinde bağımsız QA ile doğrulandı",
                    source=f"mission:{mission['mission_id']}",
                    mission_id=mission["mission_id"], verified=True)
                seen_types.add(plan_type)
                written["semantic"] += 1
            written["episodes"] += 1
            written["procedural"] += 1
        cm.metacognition(profile)
        cm.emotion(profile, pending=0, idle=True)
        if apply:
            cm.save(RUNTIME, profile)
        written["profiles"] += 1

    if apply:
        cm.expert_index(RUNTIME, departments)
        cm.mentor_pairs(RUNTIME, departments)
    written["roster"] = len(roster)
    written["applied"] = apply
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    result = sync(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False))
    if args.apply:
        from ahos import cognitive_memory as cm

        print(json.dumps(cm.summary(RUNTIME), ensure_ascii=False)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
