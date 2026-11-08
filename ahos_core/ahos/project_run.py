"""G012 — Departmanlar arası proje yürütücüsü (izole, QA kapılı).

Bir proje birden çok departmanın görevlerinden oluşur. Kurallar:
- Bağımlılıklar topolojik sırayla çalışır; döngü reddedilir.
- Her görev ancak yürütücü başarılı **ve** bağımsız QA geçerse tamamlanır.
- QA yoksa veya başarısızsa görev teslim edilmiş sayılmaz; bağımlıları bloke olur.
- Durum `runtime/projects/<project_id>/state.json` dosyasına yazılır.
- Bu modül ağ/model çağrısı yapmaz; yürütücü ve QA dışarıdan enjekte edilir.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _state_path(runtime, project_id: str) -> Path:
    return Path(runtime) / "projects" / project_id / "state.json"


def _order(tasks: list[dict]) -> list[dict]:
    remaining = {task["task_id"]: set(task.get("depends_on") or []) for task in tasks}
    known = set(remaining)
    for task_id, deps in remaining.items():
        missing = deps - known
        if missing:
            raise ValueError(f"unknown dependency for {task_id}: {sorted(missing)}")
    ordered, done = [], set()
    while remaining:
        ready = sorted(task_id for task_id, deps in remaining.items()
                       if deps.issubset(done))
        if not ready:
            raise ValueError("project has a dependency cycle")
        for task_id in ready:
            ordered.append(task_id)
            done.add(task_id)
            remaining.pop(task_id)
    by_id = {task["task_id"]: task for task in tasks}
    return [by_id[task_id] for task_id in ordered]


def run_project(runtime, *, project_id: str, manager: str,
                tasks: list[dict], executor, qa) -> dict:
    """executor(task) -> {"ok": bool, "output": str, "evidence": str, "worker": str}
    qa(task, result) -> {"ok": bool, "verifier": str, "note": str}"""

    if not project_id.strip() or not manager.strip():
        raise ValueError("project_id and manager are required")
    ordered = _order(tasks)
    state = {"schema": "ahos.project-run.v1", "project_id": project_id,
             "manager": manager, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "tasks": []}
    statuses: dict[str, str] = {}
    for task in ordered:
        blocked_by = [dep for dep in task.get("depends_on") or []
                      if statuses.get(dep) != "completed"]
        if blocked_by:
            statuses[task["task_id"]] = "blocked"
            state["tasks"].append({"task_id": task["task_id"],
                                   "department": task.get("department"),
                                   "status": "blocked",
                                   "reason": f"dependency not delivered: {blocked_by}"})
            continue
        result = executor(task) or {}
        if not result.get("ok"):
            statuses[task["task_id"]] = "failed"
            state["tasks"].append({"task_id": task["task_id"],
                                   "department": task.get("department"),
                                   "status": "failed",
                                   "worker": result.get("worker"),
                                   "reason": str(result.get("evidence") or "executor failed")})
            continue
        verification = qa(task, result) or {}
        if not verification.get("ok"):
            statuses[task["task_id"]] = "qa_failed"
            state["tasks"].append({"task_id": task["task_id"],
                                   "department": task.get("department"),
                                   "status": "qa_failed",
                                   "worker": result.get("worker"),
                                   "verifier": verification.get("verifier"),
                                   "reason": str(verification.get("note") or "QA failed")})
            continue
        if not verification.get("verifier") or verification["verifier"] == result.get("worker"):
            statuses[task["task_id"]] = "qa_failed"
            state["tasks"].append({"task_id": task["task_id"],
                                   "department": task.get("department"),
                                   "status": "qa_failed",
                                   "reason": "producer cannot verify own output"})
            continue
        statuses[task["task_id"]] = "completed"
        state["tasks"].append({"task_id": task["task_id"],
                               "department": task.get("department"),
                               "status": "completed",
                               "worker": result.get("worker"),
                               "verifier": verification["verifier"],
                               "output": str(result.get("output") or "")[:400],
                               "evidence": str(result.get("evidence") or "")[:300]})
    completed = sum(1 for row in state["tasks"] if row["status"] == "completed")
    state["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    state["summary"] = {"tasks": len(ordered), "completed": completed,
                        "failed": sum(1 for row in state["tasks"] if row["status"] == "failed"),
                        "qa_failed": sum(1 for row in state["tasks"] if row["status"] == "qa_failed"),
                        "blocked": sum(1 for row in state["tasks"] if row["status"] == "blocked")}
    state["delivered"] = completed == len(ordered)
    path = _state_path(runtime, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state
