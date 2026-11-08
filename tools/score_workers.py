"""Plan puanlamasını TÜM işçilere yayar — yalnız gözlenmiş görev kaydından.

Kullanım:
    python tools/score_workers.py            # kuru çalışma (ne değişir)
    python tools/score_workers.py --apply    # zihinlere yaz

Kaynak: company-service.db → missions.result_json.steps (gerçek yürütme kaydı).
Kural: hiçbir işçiye yapmadığı iş için puan verilmez; puan yalnız o işçinin
gerçekten yer aldığı görevlerin sonucundan (completed/blocked) türetilir.

Yazılanlar (idempotent — her koşuda tarihten yeniden hesaplanır):
  self_model.plan_scores["mission"] = {ok, fail, total_s}
  self_model.plan_scores["qa"]      = {ok, fail, total_s}   (yalnız QA işçileri)
  gözlenmiş görev olayı olmayan işçiler için mission olayları
  self_model.success_rate / best_plan_type / strategy.preferred_plan

Rapor: ahos_core/config/plan-score-spread.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
CONFIG = CORE / "config"
REPORT = CONFIG / "plan-score-spread.json"
sys.path.insert(0, str(CORE))

_EDIT = re.compile(r"dosyas[ıi]n[ıi]n sonuna|sonuna .*(ekle|yorum|satır)|başına .*(ekle|yorum)", re.I)


def _route(objective: str) -> str:
    """queue_drain ile aynı yürütme yolu etiketleri."""

    text = (objective or "").strip()
    if text.startswith("render:"):
        return "render"
    if _EDIT.search(text):
        return "simple_edit"
    from ahos.scope import should_document

    return "document" if should_document(text) else "executor"


def collect() -> tuple[dict, dict, int]:
    """(worker -> {producer, qa, department}, mission -> (status, objective, at)), taranan."""

    db = RUNTIME / "company-service.db"
    participations: dict[str, dict] = {}
    missions: dict[str, tuple[str, str, str]] = {}
    scanned = 0
    with sqlite3.connect(db) as con:
        rows = con.execute(
            "select mission_id, status, primary_department, objective, result_json, updated_at "
            "from missions where result_json is not null order by updated_at asc"
        ).fetchall()
    for mission_id, status, department, objective, raw, updated_at in rows:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        steps = payload.get("steps") or []
        if not steps:
            continue
        scanned += 1
        missions[mission_id] = (str(status), str(objective), str(updated_at))
        for step in steps:
            producer = step.get("worker_id")
            if producer:
                rec = participations.setdefault(
                    str(producer), {"producer": set(), "qa": set(),
                                    "department": str(step.get("department") or department)}
                )
                rec["producer"].add(mission_id)
            verifier = step.get("qa_worker_id")
            if verifier:
                rec = participations.setdefault(
                    str(verifier), {"producer": set(), "qa": set(),
                                    "department": str(step.get("department") or department)}
                )
                rec["qa"].add(mission_id)
    return participations, missions, scanned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="zihin dosyalarına yaz")
    args = parser.parse_args(argv)

    from ahos.worker_mind import load, save

    participations, missions, scanned = collect()
    if not participations:
        print("gözlenmiş görev adımı yok")
        return 1

    # Önce/sonra ölçümü
    before = 0
    before_workers = []
    for path in (RUNTIME / "minds").glob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if (data.get("self_model") or {}).get("plan_scores"):
            before += 1
            before_workers.append(str(data.get("worker_id")))

    results = []
    updated = 0
    total_new_events = 0

    for worker_id, kinds in sorted(participations.items()):
        participation = {
            "producer": sorted(kinds.get("producer") or ()),
            "qa": sorted(kinds.get("qa") or ()),
        }
        all_missions = sorted(
            set(participation["producer"]) | set(participation["qa"]),
            key=lambda mid: missions[mid][2],
        )
        if not all_missions:
            continue

        mind = load(RUNTIME, worker_id, str(kinds.get("department") or ""))
        model = dict(mind.self_model or {})
        scores = dict(model.get("plan_scores") or {})

        # 1) mission/qa puanları: tarihten yeniden hesapla (idempotent).
        for key, ids in (("mission", participation["producer"]), ("qa", participation["qa"])):
            if not ids:
                continue
            ok = sum(1 for mid in ids if missions[mid][0] == "completed")
            scores[key] = {"ok": ok, "fail": len(ids) - ok, "total_s": 0.0}

        # 2) gözlenmiş mission olayı olmayan işçiye olay yaz (success_rate için).
        existing = {e.get("mission_id") for e in mind.events
                    if e.get("kind") == "mission" and e.get("mission_id")}
        new_events = 0
        if not existing:
            # Zihin dosyası en fazla 200 olay tutar; en yeni 200 görevi yaz.
            for mission_id in all_missions[-200:]:
                status, objective, updated_at = missions[mission_id]
                producer = mission_id in participation["producer"]
                route = _route(objective) if producer else "qa"
                mind.events.append({
                    "at": updated_at[:19].replace("T", " ") if updated_at else
                          time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "kind": "mission",
                    "mission_id": mission_id,
                    "plan_type": route,
                    "detail": f"gözlenmiş görev {'tamam' if status == 'completed' else 'başarısız'}"
                              f" [{mission_id}]",
                    "ok": status == "completed",
                })
                new_events += 1

        model["plan_scores"] = scores
        if scores:
            best = max(
                scores.items(),
                key=lambda kv: kv[1]["ok"] / max(1, kv[1]["ok"] + kv[1]["fail"]),
            )
            model["best_plan_type"] = best[0]
            model["strategy"] = dict(model.get("strategy") or {})
            model["strategy"]["preferred_plan"] = best[0]
        model["success_rate"] = mind.success_rate
        mind.self_model = model

        after = bool(scores)
        results.append({
            "worker": worker_id,
            "department": mind.department,
            "missions": len(all_missions),
            "ok": sum(1 for mid in all_missions if missions[mid][0] == "completed"),
            "fail": sum(1 for mid in all_missions if missions[mid][0] != "completed"),
            "plan_keys": sorted(scores),
            "new_events": new_events,
            "had_plan_score": worker_id in before_workers,
            "now_plan_score": after,
        })
        if args.apply:
            save(RUNTIME, mind)
        updated += 1
        total_new_events += new_events

    after_count = sum(1 for r in results if r["now_plan_score"])
    if args.apply:
        # Gerçek durum: diskteki tüm zihinler (başka yollarla puanlananlar dahil).
        after_count = 0
        for path in (RUNTIME / "minds").glob("*.json"):
            if path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if (data.get("self_model") or {}).get("plan_scores"):
                after_count += 1
    print(f"taranan görev (adımlı): {scanned}")
    print(f"işçi: {len(participations)} · güncellenen: {updated} · yeni olay: {total_new_events}")
    print(f"plan puanlı işçi: önce {before} → sonra {after_count} (kuru={not args.apply})")
    top = sorted(results, key=lambda r: -r["missions"])[:8]
    for row in top:
        rate = round(100 * row["ok"] / max(1, row["ok"] + row["fail"]), 1)
        print(f"  {row['worker']:34} {row['missions']:4} görev · %{rate:5} · {','.join(row['plan_keys'])}")

    report = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "applied": bool(args.apply),
        "scanned_missions": scanned,
        "workers_participating": len(participations),
        "workers_before": before,
        "workers_after": after_count,
        "new_events": total_new_events,
        "rows": sorted(results, key=lambda r: (-r["missions"], r["worker"])),
    }
    CONFIG.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rapor: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
