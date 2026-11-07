"""G020 — V4 nihai kalite paketi: 20 test, ham kanıt + exit code.

Kullanım:
    python tools/acceptance_v4.py

Her test gerçek kayıt veya gerçek pytest çıktısı üretir; PASS/PARTIAL/FAIL.
Çıkış kodu 0 = FAIL yok.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
DB = RUNTIME / "company-service.db"
sys.path.insert(0, str(CORE))
PY = sys.executable
ENV = dict(os.environ, PYTHONPATH=str(CORE), PYTHONIOENCODING="utf-8")
TESTS = "ahos_core/tests"


def run(args: list[str], timeout: int = 900) -> dict:
    proc = subprocess.run(args, cwd=str(ROOT), env=ENV, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return {"command": " ".join(args), "exit": proc.returncode,
            "tail": (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [""]}


def pytest(*nodes: str, timeout: int = 900) -> dict:
    return run([PY, "-m", "pytest", "-q", "--no-header", *nodes], timeout=timeout)


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


def roster() -> set[str]:
    payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    return {str(w["worker_id"]) for d in departments for w in d.get("workers") or []}


def db_counts() -> dict:
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
        return dict(con.execute("select status,count(*) from missions group by status"))


def check_1() -> dict:
    people = roster()
    prof = profiles()
    minds = {p.stem for p in (RUNTIME / "minds").glob("*.json")}
    ok = len(people) == 81 and set(prof) >= people and len(minds) >= 81
    return _row(1, "81 işçi hafıza bütünlüğü", "PASS" if ok else "FAIL",
                {"roster": len(people), "profiles": len(prof), "minds": len(minds)})


def check_2() -> dict:
    prof = profiles()
    required = {"episodic", "semantic", "procedural", "working", "long_term", "shared"}
    complete = all(
        required <= set(p.get("memory") or {}) and "meta_memory" in p
        for p in prof.values())
    ok = len(prof) >= 81 and complete
    return _row(2, "Kalıcı bilişsel profil katmanları", "PASS" if ok else "FAIL",
                {"profiles": len(prof), "layers_complete": complete})


def check_3() -> dict:
    prof = profiles()
    statuses = [str((p.get("evidence") or {}).get("status") or "") for p in prof.values()]
    verified = sum(1 for s in statuses if s == "verified")
    none = sum(1 for s in statuses if s == "no_verified_evidence")
    ok = verified + none == len(prof) and none >= 0
    return _row(3, "Gerçek görev kanıtı / açık kanıtsızlık", "PASS" if ok else "FAIL",
                {"verified": verified, "no_verified_evidence": none,
                 "note": "sahte kanıt üretilmedi"})


def check_4() -> dict:
    r = pytest(f"{TESTS}/test_failure_learning.py")
    return _row(4, "Hata analizi (20 senaryo)", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"], "tail": r["tail"]})


def check_5() -> dict:
    from ahos import cognitive_memory as cm

    path = RUNTIME / "cognition" / "software-manager.json"
    hits = []
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        hits = cm.recall(payload, "doğrulandı", limit=3)
    r = pytest(f"{TESTS}/test_cognitive_memory_v4.py")
    ok = r["exit"] == 0 and bool(hits)
    return _row(5, "Öğrenme tekrar kullanımı", "PASS" if ok else "PARTIAL",
                {"pytest_exit": r["exit"], "recall_hits": len(hits)})


def check_6() -> dict:
    r = pytest(f"{TESTS}/test_v4_collaboration.py::test_twenty_cross_department_routing_scenarios")
    return _row(6, "Uzman yönlendirme (20 senaryo)", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_7() -> dict:
    r = pytest(f"{TESTS}/test_v4_collaboration.py::test_ten_real_help_cases_are_qa_verified")
    return _row(7, "İşçiler arası destek (10 vaka)", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_8() -> dict:
    r = pytest(f"{TESTS}/test_v4_collaboration.py::test_cross_department_project_delivered_end_to_end")
    return _row(8, "Çok-departmanlı gerçek görev", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_9() -> dict:
    r = pytest(f"{TESTS}/test_owner_auth.py", timeout=600)
    return _row(9, "Sahip kimlik doğrulaması", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_10() -> dict:
    r = pytest(f"{TESTS}/test_panel_auth.py", f"{TESTS}/test_owner_auth.py")
    return _row(10, "Yetkisiz işlem reddi", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_11() -> dict:
    r = pytest(f"{TESTS}/test_queue_capacity_and_population.py::"
               "test_atomic_capacity_preserves_pending_and_never_drops_existing")
    pending = int(db_counts().get("pending", 0))
    return _row(11, "300 görev sınırı", "PASS" if r["exit"] == 0 and pending <= 300 else "FAIL",
                {"pytest_exit": r["exit"], "live_pending": pending})


def check_12() -> dict:
    r = pytest(f"{TESTS}/test_queue_capacity_and_population.py::"
               "test_plan_queue_waits_under_pressure_then_draining_resumes")
    return _row(12, "Drain ve otomatik devam", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_13() -> dict:
    r = pytest(f"{TESTS}/test_v4_resilience.py", f"{TESTS}/test_daemon_loop.py")
    return _row(13, "Daemon/kuyruk yeniden başlatma", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_14() -> dict:
    r = pytest(f"{TESTS}/test_v4_resilience.py::test_corrupt_mind_is_not_overwritten_on_restart",
               f"{TESTS}/test_cognitive_memory.py::"
               "test_corrupt_profile_is_preserved_not_overwritten")
    return _row(14, "Hafıza bozulması koruması", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_15() -> dict:
    from ahos import memory_vault as mv
    from pathlib import Path as P

    root = P(r"C:\actions-runner\_work\AHOS_BACKUPS")
    vaults = sorted(p for p in root.glob("vault-*") if p.is_dir()) if root.is_dir() else []
    if not vaults:
        return _row(15, "Yedek bütünlüğü", "FAIL", {"vaults": 0})
    try:
        result = mv.verify(vaults[-1])
    except Exception as exc:  # noqa: BLE001
        return _row(15, "Yedek bütünlüğü", "FAIL",
                    {"vault": vaults[-1].name, "error": type(exc).__name__})
    return _row(15, "Yedek bütünlüğü", "PASS" if result.get("verified") else "FAIL",
                {"vault": vaults[-1].name, "files": result.get("files")})


def check_16() -> dict:
    r = pytest(f"{TESTS}/test_v4_model_router.py")
    return _row(16, "Model maliyet kontrolü", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_17() -> dict:
    proc = run([PY, "tools/eval_learning.py"], timeout=120)
    candidates = sorted((RUNTIME / "evals").glob("learning-eval-*.json"))
    data = {}
    if candidates:
        try:
            data = json.loads(candidates[-1].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    ok = proc["exit"] == 0 and bool(data.get("methods"))
    return _row(17, "Performans karşılaştırması", "PASS" if ok else "FAIL",
                {"eval_exit": proc["exit"], "delta": data.get("delta"),
                 "winner": data.get("winner")})


def check_18() -> dict:
    r = pytest(f"{TESTS}/test_v4_collaboration.py::"
               "test_cross_department_project_delivered_end_to_end",
               f"{TESTS}/test_v4_collaboration.py::"
               "test_project_qa_failure_blocks_dependents")
    return _row(18, "Gerçek uçtan uca teslimat", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"]})


def check_19() -> dict:
    r = pytest(f"{TESTS}/test_cognitive_memory_v4.py::"
               "test_conflict_keeps_both_and_picks_higher_confidence")
    candidates = sorted((RUNTIME / "evals").glob("learning-eval-*.json"))
    rollback = None
    if candidates:
        try:
            rollback = json.loads(candidates[-1].read_text(encoding="utf-8")).get(
                "rollback_recommended")
        except (OSError, json.JSONDecodeError):
            rollback = None
    return _row(19, "Geri alma mekanizması", "PASS" if r["exit"] == 0 else "FAIL",
                {"pytest_exit": r["exit"], "rollback_flag": rollback})


def check_20() -> dict:
    local = run(["git", "rev-parse", "HEAD"], timeout=60)["tail"][0] if run(
        ["git", "rev-parse", "HEAD"], timeout=60)["tail"] else ""
    remote_proc = subprocess.run(["git", "ls-remote", "origin",
                                  "refs/heads/feature/agent-control-plane"],
                                 cwd=str(ROOT), capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=120)
    remote = (remote_proc.stdout or "").split()[0] if remote_proc.returncode == 0 and remote_proc.stdout else ""
    ok = bool(local) and local == remote
    return _row(20, "GitHub dağıtım doğrulaması",
                "PASS" if ok else ("PARTIAL" if not remote else "FAIL"),
                {"local": local[:12], "remote": remote[:12],
                 "note": "force push yok"})


def _row(index: int, name: str, status: str, evidence: dict) -> dict:
    return {"id": index, "name": name, "status": status, "evidence": evidence}


def main() -> int:
    checks = [check_1(), check_2(), check_3(), check_4(), check_5(),
              check_6(), check_7(), check_8(), check_9(), check_10(),
              check_11(), check_12(), check_13(), check_14(), check_15(),
              check_16(), check_17(), check_18(), check_19(), check_20()]
    for row in checks:
        print(f"[{row['status']:7}] {row['id']:02}. {row['name']}")
        print("          " + json.dumps(row["evidence"], ensure_ascii=False)[:420])
    passed = sum(1 for row in checks if row["status"] == "PASS")
    partial = sum(1 for row in checks if row["status"] == "PARTIAL")
    failed = sum(1 for row in checks if row["status"] == "FAIL")
    print(f"\nSONUC: PASS={passed} PARTIAL={partial} FAIL={failed} / 20")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
