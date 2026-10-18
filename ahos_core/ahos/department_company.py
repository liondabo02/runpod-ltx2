"""Bridge persisted company missions to existing workforce orchestration.

Completion here means a reviewed local draft artifact, never deployment,
publication, payment or other execution of the owner's business objective.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .autonomous_company import CompanyLoop, PersistentMissionQueue
from .company_runtime import OrchestratedMissionExecutor
from .mission_orchestrator import MissionStepSpec, MultiWorkerMissionOrchestrator
from .virtual_workforce import VirtualWorkforceRegistry, WorkerRole, default_virtual_workforce
from .worker_runtime import QaExecutor, WorkerExecutor


def build_department_company_loop(
    runtime_dir: Path, *, executors: Mapping[str, WorkerExecutor],
    qa_executor: QaExecutor,
) -> CompanyLoop:
    """Reuse mission leases, manager routing and worker QA for draft requests."""
    profiles = default_virtual_workforce()
    registry = VirtualWorkforceRegistry(profiles)
    managers = {p.worker_id: p.department for p in profiles
                if p.role is WorkerRole.DEPARTMENT_MANAGER}
    specialists = {p.department: p for p in profiles
                   if p.role is not WorkerRole.DEPARTMENT_MANAGER}

    def planner(mission_id: str, objective: str, manager_id: str):
        department = managers[manager_id]
        specialist = specialists[department]
        if specialist.worker_id not in executors:
            raise ValueError(f"no draft executor for department {department}")
        return (MissionStepSpec(
            step_id="department-draft", department=department,
            title=("Prepare a local draft artifact addressing this objective; "
                   "do not claim the objective has been executed: " + objective),
            required_capabilities=specialist.capabilities,
        ),)

    orchestrator = MultiWorkerMissionOrchestrator(
        registry, manager_planner=planner, executors=executors,
        qa_executor=qa_executor,
    )
    return CompanyLoop(
        queue=PersistentMissionQueue(Path(runtime_dir) / "company-service.db"),
        executor=OrchestratedMissionExecutor(orchestrator),
        owner="AHOS-DEPARTMENT-DRAFTS", lease_seconds=3600,
    )


def department_task_id(mission_id: str) -> str:
    import hashlib
    return "COMPANY-" + hashlib.sha256(mission_id.encode("utf-8")).hexdigest()[:32]


def build_persistent_department_loop(runtime_dir: Path, department_runtime) -> CompanyLoop:
    """Existing mission queue delegates draft production to the persistent runtime.

    Only objectives explicitly prefixed ``draft:`` can complete after artifact
    approval. Broader objectives remain waiting: producing a draft is not the
    execution of a business mission.
    """
    from .department_runtime import DepartmentTask
    from .mission_orchestrator import MissionResult, MissionStatus
    from .worker_runtime import WorkerExecutionResult, QaExecutionResult
    import hashlib
    import json

    def records():
        return {t["task_id"]: t for t in department_runtime.snapshot()["tasks"]}

    def execute(item, worker_id):
        # The existing manager adds its mission prefix to task IDs.
        mission_id = item.task_id.rsplit(":department-draft", 1)[0]
        identifier = department_task_id(mission_id)
        task = records().get(identifier)
        if task is None:
            department_runtime.enqueue(DepartmentTask(identifier, item.department, item.title))
        department_runtime.run_once()
        task = records()[identifier]
        if not task.get("artifact"):
            return WorkerExecutionResult(item.task_id, worker_id, False,
                                         "Department draft pending: " + task["status"])
        return WorkerExecutionResult(item.task_id, worker_id, True,
                                     "Local draft awaiting owner review",
                                     (str(department_runtime.root / task["artifact"]),))

    def qa(item, result, worker_id):
        passed = False
        if len(result.artifacts) == 1:
            path = Path(result.artifacts[0])
            try:
                body = path.read_bytes()
                payload = json.loads(body)
                mission_id = item.task_id.rsplit(":department-draft", 1)[0]
                task = records()[department_task_id(mission_id)]
                passed = (path.resolve().is_relative_to(department_runtime.root)
                          and hashlib.sha256(body).hexdigest() == task.get("artifact_hash")
                          and payload.get("execution_performed") is False
                          and payload.get("department") == item.department)
            except (OSError, ValueError, KeyError):
                pass
        return QaExecutionResult(item.task_id, worker_id, passed,
                                 "Draft integrity checked" if passed else "Draft integrity failed")

    profiles = default_virtual_workforce()
    executors = {p.worker_id: execute for p in profiles
                 if p.role is not WorkerRole.DEPARTMENT_MANAGER}
    loop = build_department_company_loop(runtime_dir, executors=executors, qa_executor=qa)
    orchestrated = loop.executor

    def executor(mission):
        result = orchestrated(mission)
        task = records().get(department_task_id(mission.mission_id), {})
        if task.get("status") in {"blocked", "retries_exhausted", "owner_rejected"}:
            return MissionResult(mission.mission_id, mission.objective, result.manager_id,
                                 MissionStatus.BLOCKED, result.steps,
                                 "Department draft " + task["status"])
        return MissionResult(
            mission.mission_id, mission.objective, result.manager_id,
            MissionStatus.WAITING_OWNER_APPROVAL, result.steps,
            "Department draft " + str(task.get("status", "pending"))
            + "; business objective has not been executed",
        )
    loop.executor = executor
    return loop


def reconcile_department_missions(loop: CompanyLoop, department_runtime) -> int:
    """Complete explicit draft requests after evidence-bound owner approval."""
    import hashlib
    import json
    from .autonomous_company import QueueStatus
    tasks = {t["task_id"]: t for t in department_runtime.snapshot()["tasks"]}
    count = 0
    for mission in loop.queue.list():
        if mission.status is not QueueStatus.WAITING_OWNER_APPROVAL:
            continue
        task = tasks.get(department_task_id(mission.mission_id))
        if not task:
            continue
        target = None
        reason = None
        if task["status"] == "owner_rejected":
            target, reason = QueueStatus.BLOCKED, "Department draft rejected by owner"
        elif task["status"] == "owner_approved" and mission.objective.lstrip().lower().startswith("draft:"):
            path = (department_runtime.root / str(task.get("artifact", ""))).resolve()
            try:
                valid = (path.is_relative_to(department_runtime.root)
                         and hashlib.sha256(path.read_bytes()).hexdigest() == task.get("artifact_hash"))
                for dep_id, dep_hash in task.get("dependency_evidence", {}).items():
                    dep = tasks.get(dep_id, {})
                    dep_path = (department_runtime.root / str(dep.get("artifact", ""))).resolve()
                    valid = valid and (dep.get("status") != "owner_rejected"
                        and dep.get("artifact_hash") == dep_hash
                        and dep_path.is_relative_to(department_runtime.root)
                        and hashlib.sha256(dep_path.read_bytes()).hexdigest() == dep_hash)
            except OSError:
                valid = False
            if valid:
                target, reason = QueueStatus.COMPLETED, "Owner approved the requested draft; external execution not performed"
            else:
                target, reason = QueueStatus.BLOCKED, "Approved draft evidence changed"
        if target is not None:
            payload = json.loads(mission.result_json or "{}")
            payload.update(status=target.value, reason=reason)
            with loop.queue._connect() as conn:
                conn.execute("UPDATE missions SET status=?, updated_at=?, result_json=? WHERE mission_id=? AND status=?",
                             (target.value, task["updated_at"], json.dumps(payload), mission.mission_id,
                              QueueStatus.WAITING_OWNER_APPROVAL.value))
            count += 1
    return count
