"""V4 Faz 0 envanteri: bileşenleri gerçek kaynak + runtime kanıtıyla sınıflandırır.

Çıktı:
  ahos_core/config/inventory-v4.json   (makine okunur)
  docs/ENVANTER-V4.md                  (insan okunur özet tablo)

Sınıflar: mevcut · test edildi · yarim · calismiyor · eksik
Kural: "test edildi" yalnız test dosyası olan ve son tam pakette geçen
bileşenler için kullanılır; kanıtsız iddia yok.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
AHOS = CORE / "ahos"
TESTS = CORE / "tests"
RUNTIME = CORE / "runtime"
CFG = CORE / "config"
DB = RUNTIME / "company-service.db"

COMPONENTS = [
    ("worker_mind", "ahos_core/ahos/worker_mind.py"),
    ("cognitive_memory", "ahos_core/ahos/cognitive_memory.py"),
    ("memory_vault", "ahos_core/ahos/memory_vault.py"),
    ("cognition", "ahos_core/ahos/cognition.py"),
    ("agent_growth", "ahos_core/ahos/agent_growth.py"),
    ("self_learning", "ahos_core/ahos/self_learning.py"),
    ("learning_feedback", "ahos_core/ahos/learning_feedback.py"),
    ("consensus", "ahos_core/ahos/consensus.py"),
    ("commune", "ahos_core/ahos/commune.py"),
    ("queue_drain", "ahos_core/ahos/queue_drain.py"),
    ("queue_budget", "ahos_core/ahos/queue_budget.py"),
    ("autonomous_company", "ahos_core/ahos/autonomous_company.py"),
    ("initiative", "ahos_core/ahos/initiative.py"),
    ("improvement_cycle", "ahos_core/ahos/improvement_cycle.py"),
    ("owner_auth", "ahos_core/ahos/owner_auth.py"),
    ("panel_auth", "ahos_core/ahos/panel_auth.py"),
    ("control_center", "ahos_core/ahos/control_center.py"),
    ("daemon", "ahos_core/ahos/daemon.py"),
    ("knowledge", "ahos_core/ahos/knowledge.py"),
    ("research_store", "ahos_core/ahos/research_store.py"),
    ("llm_executor", "ahos_core/ahos/llm_executor.py"),
    ("premium", "ahos_core/ahos/premium.py"),
    ("office_3d", "ahos_core/ahos/office_3d.py"),
    ("office_server", "ahos_core/ahos/office_server.py"),
    ("research_loop", "tools/research_loop.py"),
    ("cognition_sync", "tools/cognition_sync.py"),
    ("collective_loop", "tools/collective_loop.py"),
    ("cognition_init", "tools/cognition_init.py"),
    ("eval_learning", "tools/eval_learning.py"),
    ("acceptance_advanced", "tools/acceptance_advanced.py"),
]


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        return proc.returncode, (proc.stdout or proc.stderr)[-4000:]
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def _grep(pattern: str, paths: list[Path]) -> int:
    hits = 0
    for path in paths:
        if path.is_file():
            try:
                hits += len(re.findall(pattern, path.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return hits


def _db_counts() -> dict:
    if not DB.is_file():
        return {}
    try:
        with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
            counts = dict(con.execute("select status,count(*) from missions group by status"))
            triggers = [row[0] for row in con.execute(
                "select name from sqlite_master where type='trigger'")]
        return {"missions": counts, "triggers": triggers}
    except sqlite3.Error:
        return {}


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _runtime_evidence() -> dict:
    minds = [p for p in (RUNTIME / "minds").glob("*.json") if not p.name.startswith("_")]
    profiles = [p for p in (RUNTIME / "cognition").glob("*.json")
                if not p.name.startswith(("_", "."))]
    plan_scored = 0
    for path in minds:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("self_model") or {}).get("plan_scores"):
            plan_scored += 1
    verified = no_evidence = 0
    for path in profiles:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        status = (data.get("evidence") or {}).get("status")
        verified += status == "verified"
        no_evidence += status == "no_verified_evidence"
    learning = sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                   for p in (RUNTIME / "learning").glob("*.jsonl"))
    research = sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                   for p in (RUNTIME / "research").glob("*.jsonl"))
    knowledge = len(list((RUNTIME / "knowledge" / "research").rglob("*.md"))) \
        if (RUNTIME / "knowledge" / "research").is_dir() else 0
    owner = _json(RUNTIME / "owner" / "owner-auth.json", None)
    sessions = _json(RUNTIME / "owner" / "owner-sessions.json", {"sessions": []})
    audit_lines = 0
    audit_path = RUNTIME / "owner" / "audit.jsonl"
    if audit_path.is_file():
        audit_lines = len(audit_path.read_text(encoding="utf-8", errors="replace").splitlines())
    backups = Path(r"C:\actions-runner\_work\AHOS_BACKUPS")
    vaults = [p for p in backups.glob("vault-*") if p.is_dir()] if backups.is_dir() else []
    return {
        "minds": len(minds), "cognition_profiles": len(profiles),
        "plan_scored_workers": plan_scored,
        "profiles_verified": verified, "profiles_no_evidence": no_evidence,
        "learning_records": learning, "research_records": research,
        "knowledge_docs": knowledge,
        "owner_configured": owner is not None,
        "owner_sessions": len(sessions.get("sessions") or []),
        "owner_audit_lines": audit_lines,
        "memory_vaults": len(vaults),
        "latest_vault": sorted(vaults)[-1].name if vaults else "",
    }


def _services() -> list[str]:
    code, out = _run(["powershell", "-NoProfile", "-Command",
                      "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                      "Where-Object { $_.CommandLine -match 'ahos.daemon|research_loop|"
                      "cognition_sync|collective_loop|office_server|control_center' } | "
                      "ForEach-Object { $_.CommandLine }"], ROOT, timeout=60)
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    kinds = set()
    for line in lines:
        for key in ("ahos.daemon", "research_loop", "cognition_sync", "collective_loop",
                    "office_server", "control_center"):
            if key in line:
                kinds.add(key)
    return sorted(kinds)


def build() -> dict:
    departments = _json(RUNTIME / "departments.json", {"departments": []})
    deps = departments.get("departments") if isinstance(departments, dict) else departments
    workers = sum(len(d.get("workers") or []) for d in deps)
    all_ahos = list(AHOS.glob("*.py"))
    rows = []
    for name, relative in COMPONENTS:
        path = ROOT / relative
        exists = path.is_file()
        tests = sorted(p.name for p in TESTS.glob(f"test_{name}*.py"))
        imported = _grep(rf"from \.{name} import|import {name}\b", all_ahos)
        status = "eksik"
        evidence = []
        if exists:
            compile_code, _ = _run([sys.executable, "-m", "py_compile", str(path)], ROOT, 60)
            if compile_code != 0:
                status = "calismiyor"
                evidence.append("py_compile failed")
            elif tests:
                status = "test edildi"
                evidence.append("tests: " + ", ".join(tests[:2]))
            elif imported:
                status = "mevcut"
                evidence.append(f"{imported} import referansı")
            else:
                status = "yarim"
                evidence.append("test/import kanıtı yok")
        rows.append({"component": name, "path": relative, "status": status,
                     "tests": tests, "imports": imported, "evidence": evidence})
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git": {"head": _run(["git", "rev-parse", "HEAD"], ROOT)[1].strip(),
                "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], ROOT)[1].strip()},
        "departments": len(deps), "workers": workers,
        "components": rows,
        "db": _db_counts(),
        "runtime": _runtime_evidence(),
        "services": _services(),
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# AHOS V4 — Faz 0 Envanteri",
        "",
        f"- Üretim: {payload['at']}",
        f"- Branch/HEAD: `{payload['git']['branch']}` · `{payload['git']['head'][:12]}`",
        f"- Departman: **{payload['departments']}** · İşçi: **{payload['workers']}**",
        f"- Çalışan servisler: {', '.join(payload['services']) or 'yok'}",
        "",
        "## Bileşen sınıflandırması",
        "",
        "| Bileşen | Durum | Test | Kanıt |",
        "|---|---|---|---|",
    ]
    for row in payload["components"]:
        lines.append(f"| `{row['component']}` | {row['status']} | "
                     f"{', '.join(row['tests'][:2]) or '—'} | {'; '.join(row['evidence'])} |")
    rt = payload["runtime"]
    lines += [
        "",
        "## Runtime kanıtı",
        "",
        f"- Zihin dosyası: **{rt['minds']}** · bilişsel profil: **{rt['cognition_profiles']}**",
        f"- `plan_scores` dolu işçi: **{rt['plan_scored_workers']}**",
        f"- Kanıtlı profil: **{rt['profiles_verified']}** · kanıtsız: **{rt['profiles_no_evidence']}**",
        f"- Öğrenme kaydı: **{rt['learning_records']}** · araştırma: **{rt['research_records']}** · bilgi belgesi: **{rt['knowledge_docs']}**",
        f"- Sahip kurulumu: **{rt['owner_configured']}** · oturum: **{rt['owner_sessions']}** · denetim satırı: **{rt['owner_audit_lines']}**",
        f"- Memory vault: **{rt['memory_vaults']}** · son: `{rt['latest_vault']}`",
        "",
        "## Kuyruk",
        "",
        "```json",
        json.dumps(payload.get("db"), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    payload = build()
    CFG.mkdir(parents=True, exist_ok=True)
    (CFG / "inventory-v4.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "docs" / "ENVANTER-V4.md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"components": len(payload["components"]),
                      "workers": payload["workers"],
                      "services": payload["services"],
                      "out": "docs/ENVANTER-V4.md"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
