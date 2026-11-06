"""10 kabul testini gerçek çıktıyla denetler ve raporlar.

Kullanım:
    python tools/acceptance_advanced.py

Çıkış kodu 0 = hepsi PASS; 1 = FAIL/PARTIAL var.
Her kontrol için ham kanıt (sayaç, dosya, komut, exit code) yazdırılır.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
DB = RUNTIME / "company-service.db"
PY = sys.executable
ENV = dict(os.environ, PYTHONPATH=str(CORE), PYTHONIOENCODING="utf-8",
           GIT_AUTHOR_NAME="AHOS CI", GIT_AUTHOR_EMAIL="ci@example.invalid",
           GIT_COMMITTER_NAME="AHOS CI", GIT_COMMITTER_EMAIL="ci@example.invalid")


def run(args: list[str], timeout: int = 600) -> dict:
    proc = subprocess.run(args, cwd=str(ROOT), env=ENV, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return {"command": " ".join(args), "exit": proc.returncode,
            "stdout": proc.stdout[-1500:], "stderr": proc.stderr[-800:]}


def departments() -> list[dict]:
    payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
    return payload.get("departments") if isinstance(payload, dict) else payload


def profiles() -> dict[str, dict]:
    rows = {}
    for path in (RUNTIME / "cognition").glob("*.json"):
        if path.name.startswith(("_", ".")):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows[str(payload.get("worker_id"))] = payload
    return rows


def check_1() -> dict:
    roster = {str(w.get("worker_id")) for d in departments() for w in d.get("workers") or []}
    prof = profiles()
    minds = {p.stem for p in (RUNTIME / "minds").glob("*.json")}
    complete = all(
        {"episodic", "semantic", "procedural", "working"} <= set(prof[w]["memory"]) and
        "metacognition" in prof[w] and "emotion" in prof[w]
        for w in roster if w in prof
    )
    ok = len(roster) == 81 and set(prof) >= roster and complete
    return {"id": 1, "name": "81/81 kalıcı hafıza + gelişim profili",
            "status": "PASS" if ok else "FAIL",
            "evidence": {"roster": len(roster), "profiles": len(prof),
                         "minds": len(minds), "schema_complete": complete}}


def check_2() -> dict:
    prof = profiles()
    valid = {"verified", "no_verified_evidence"}
    bad = [w for w, p in prof.items() if (p.get("evidence") or {}).get("status") not in valid]
    verified = [w for w, p in prof.items() if (p.get("evidence") or {}).get("status") == "verified"]
    no_evidence = [w for w, p in prof.items()
                   if (p.get("evidence") or {}).get("status") == "no_verified_evidence"]
    ok = not bad and len(verified) + len(no_evidence) == len(prof)
    return {"id": 2, "name": "Her öğrenme kaydı kanıtlı veya açıkça kanıtsız",
            "status": "PASS" if ok else "FAIL",
            "evidence": {"verified": len(verified), "no_verified_evidence": len(no_evidence),
                         "invalid": bad[:5]}}


def check_3() -> dict:
    test = run([PY, "-m", "pytest", "-q", "--no-header",
                "ahos_core/tests/test_observed_learning.py::"
                "test_twenty_observed_tasks_score_more_than_ten_actual_workers"])
    live = 0
    try:
        for path in (RUNTIME / "minds").glob("*.json"):
            if path.name.startswith("_"):
                continue
            if (json.loads(path.read_text(encoding="utf-8")).get("self_model") or {}).get("plan_scores"):
                live += 1
    except (OSError, json.JSONDecodeError):
        pass
    ok = test["exit"] == 0 and live >= 11
    return {"id": 3, "name": "20 görevde >=11 işçi plan_scores",
            "status": "PASS" if ok else "FAIL",
            "evidence": {"pytest_exit": test["exit"], "live_plan_score_workers": live}}


def check_4() -> dict:
    path = RUNTIME / "minds" / "conversations.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()[-20:]
            if line.strip()] if path.is_file() else []
    matched = [row for row in rows
               if "CMD-" in str(row.get("topic") or "") or "mission_id=" in str(row.get("body") or "")]
    grounded = [row for row in matched if "objective=" in str(row.get("body") or "")]
    ok = len(matched) >= 10
    return {"id": 4, "name": "Son 20 konuşmada >=10 mission_id",
            "status": "PASS" if ok else "FAIL",
            "evidence": {"last20": len(rows), "with_mission_id": len(matched),
                         "with_objective": len(grounded)}}


def check_5() -> dict:
    with sqlite3.connect(DB) as con:
        pending = con.execute("select count(*) from missions where status='pending'").fetchone()[0]
        triggers = [row[0] for row in con.execute(
            "select name from sqlite_master where type='trigger'")]
    capacity = [name for name in triggers if "capac" in name.lower() or "pending" in name.lower()]
    try:
        probe = run([PY, "-c", "from ahos.autonomous_company import MAX_PENDING_MISSIONS;"
                               "print(MAX_PENDING_MISSIONS)"], timeout=60)
        constant = probe["stdout"].strip() if probe["exit"] == 0 else ""
    except Exception:  # noqa: BLE001
        constant = ""
    ok = pending <= 300
    status = "PASS" if ok and (capacity or constant) else ("PARTIAL" if ok else "FAIL")
    return {"id": 5, "name": "Eşzamanlı üretimde pending <= 300",
            "status": status, "evidence": {"pending": pending, "limit": constant or 300,
                                           "capacity_triggers": capacity[:3]}}


def check_6() -> dict:
    test = run([PY, "-m", "pytest", "-q", "--no-header",
                "ahos_core/tests/test_queue_capacity_and_population.py::"
                "test_plan_queue_waits_under_pressure_then_draining_resumes"])
    return {"id": 6, "name": "Drain sonrası otomatik kapasite dengeleme",
            "status": "PASS" if test["exit"] == 0 else "PARTIAL",
            "evidence": {"pytest_exit": test["exit"],
                         "note": "capacity modülü çalışma ağacında; commit bekliyor olabilir"}}


def check_7() -> dict:
    test = run([PY, "-m", "pytest", "-q", "--no-header", "ahos_core/tests/test_owner_auth.py"])
    return {"id": 7, "name": "Yetkisiz kullanıcı/ajan onay veremiyor",
            "status": "PASS" if test["exit"] == 0 else "FAIL",
            "evidence": {"pytest_exit": test["exit"]}}


def check_8() -> dict:
    test = run([PY, "-m", "pytest", "-q", "--no-header",
                "ahos_core/tests/test_cognitive_memory.py::"
                "test_corrupt_profile_is_preserved_not_overwritten",
                "ahos_core/tests/test_cognitive_memory.py::"
                "test_profile_persists_and_existing_data_is_not_reset"])
    minds = len(list((RUNTIME / "minds").glob("*.json")))
    ok = test["exit"] == 0 and minds >= 81
    return {"id": 8, "name": "Eski hafıza ve görev kayıtları korunuyor",
            "status": "PASS" if ok else "FAIL",
            "evidence": {"pytest_exit": test["exit"], "mind_files": minds}}


def check_9() -> dict:
    eval_run = run([PY, "tools/eval_learning.py"], timeout=120)
    try:
        payload = json.loads(eval_run["stdout"])
    except json.JSONDecodeError:
        payload = {}
    methods = payload.get("methods") or {}
    ok = eval_run["exit"] == 0 and "history_rate" in methods and "evidence_grounded" in methods
    return {"id": 9, "name": "Yeni öğrenme yöntemi ayrı değerlendirmede karşılaştırıldı",
            "status": "PASS" if ok else "FAIL",
            "evidence": {"pytest_exit": eval_run["exit"], "methods": methods,
                         "delta": payload.get("delta"),
                         "rollback_recommended": payload.get("rollback_recommended")}}


def check_10(full: bool = False) -> dict:
    # runtime/ altındaki gömülü site-packages taranmaz; yalnız kendi kodumuz.
    compile_run = run([PY, "-m", "compileall", "-q",
                       "ahos_core/ahos", "ahos_core/tests", "tools"], timeout=300)
    if full:
        tests = run([PY, "-m", "pytest", "-q", "--no-header", "ahos_core/tests"], timeout=1800)
    else:
        tests = run([PY, "-m", "pytest", "-q", "--no-header",
                     "ahos_core/tests/test_cognitive_memory.py",
                     "ahos_core/tests/test_owner_auth.py",
                     "ahos_core/tests/test_queue_drain.py",
                     "ahos_core/tests/test_observed_learning.py"], timeout=600)
    ok = compile_run["exit"] == 0 and tests["exit"] == 0
    return {"id": 10, "name": "Tüm testler + derleme" + (" (full)" if full else " (odaklı)"),
            "status": "PASS" if ok else "FAIL",
            "evidence": {"compile_exit": compile_run["exit"], "pytest_exit": tests["exit"],
                         "full": full,
                         "pytest_tail": tests["stdout"].strip().splitlines()[-1:] or [""]}}


def main() -> int:
    full = "--full" in sys.argv[1:]
    checks = [check_1(), check_2(), check_3(), check_4(), check_5(),
              check_6(), check_7(), check_8(), check_9(), check_10(full)]
    for row in checks:
        print(f"[{row['status']:7}] {row['id']:2}. {row['name']}")
        print("          " + json.dumps(row["evidence"], ensure_ascii=False)[:400])
    passed = sum(1 for row in checks if row["status"] == "PASS")
    partial = sum(1 for row in checks if row["status"] == "PARTIAL")
    failed = sum(1 for row in checks if row["status"] == "FAIL")
    print(f"\nSONUC: PASS={passed} PARTIAL={partial} FAIL={failed} / 10")
    return 0 if passed == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
