"""Drain already-queued missions.

The daemon's scheduler generates *new* work from CEO directives; missions that
are already sitting in the queue (for example rows reopened by the repair tool)
are never claimed, so they stay ``pending`` forever. This module claims those
rows directly and runs them through the same owner-console execution path.
"""

from __future__ import annotations

import time
from pathlib import Path

from .autonomous_company import PersistentMissionQueue, QueueStatus
from .mission_orchestrator import MissionResult, MissionStatus


def _scoring_worker(result: MissionResult, department: str) -> str:
    """Credit a worker with an observed execution, not just an assignment.

    Fast-path edits have no step record, so the department manager remains
    their accountable worker. Never count the independent QA verifier.
    """
    for step in result.steps:
        worker_id = getattr(step, "worker_id", None)
        if worker_id and getattr(step, "worker_summary", None) is not None:
            return str(worker_id)
    return str(result.manager_id or f"{department}-manager")


def drain(
    console,
    *,
    owner: str = "queue-drainer",
    limit: int = 10,
    dry_run: bool = False,
) -> dict[str, object]:
    """Claim pending missions (oldest first) and execute them.

    Returns a report with the missions that were executed. Missions whose
    department no longer exists are blocked instead of being dropped.
    """

    # Konsolun kuyruk nesnesine güvenme: her zaman runtime veritabanına bağlan.
    # (Konsol farklı bir dosyaya bağlıysa drain hiç görev alamıyordu.)
    from pathlib import Path as _Path2

    queue: PersistentMissionQueue = PersistentMissionQueue(
        _Path2(console.runtime_dir) / "company-service.db"
    )

    if dry_run:
        pending = [
            mission
            for mission in queue.list()
            if mission.status is QueueStatus.PENDING
        ]
        return {
            "executed": [],
            "blocked": [],
            "skipped": min(len(pending), limit),
            "would_run": [m.mission_id for m in pending[:limit]],
        }

    executed: list[str] = []
    blocked: list[str] = []
    skipped = 0

    for _ in range(max(1, limit)):
        claimed = queue.claim_next(owner=owner, lease_seconds=900)
        if claimed is None:
            break
        started_at = time.monotonic()
        spec = console.book.get(claimed.primary_department)
        if spec is None:
            queue.block(
                claimed.mission_id,
                owner=owner,
                result=MissionResult(
                    mission_id=claimed.mission_id,
                    objective=claimed.objective,
                    manager_id=None,
                    status=MissionStatus.BLOCKED,
                    steps=(),
                    reason=f"departman artık yok: {claimed.primary_department}",
                ),
            )
            blocked.append(claimed.mission_id)
            continue

        # HIZLI YOL: tam tanımlı ekleme görevi ise modeli hiç çağırma.
        # Console kendi yürütücüsünü kurduğu için sistem yolu atlanıyor;
        # düzenleme doğrudan uygulanıyor (saniyeler içinde biter).
        fast_done = False
        result = None
        try:
            project = console._project_for_department(spec.department_id)
            from .scope import classify
            if (project is not None and not claimed.objective.startswith("render:")
                    and classify(claimed.objective) == "deterministic"):
                from .simple_edits import apply_simple_edit, parse_simple_edit

                project_root = project.work_path or project.path
                edit = parse_simple_edit(project_root, claimed.objective)
                if edit is not None:
                    target = Path(project_root) / edit.path
                    before = target.read_text(encoding="utf-8", errors="replace")
                    ok, detail = apply_simple_edit(project_root, edit)
                    after = target.read_text(encoding="utf-8", errors="replace")
                    if edit.mode == "append":
                        expected = before if not before or before.endswith("\n") else before + "\n"
                        expected += edit.text
                        if not expected.endswith("\n"):
                            expected += "\n"
                    else:
                        expected = edit.text + "\n" + before
                    # Independent read-back verification: an unchanged or
                    # unexpected file is never a completed delivery.
                    verified = bool(ok and after != before and after == expected)
                    result = MissionResult(
                        mission_id=claimed.mission_id,
                        objective=claimed.objective,
                        manager_id=None,
                        status=MissionStatus.COMPLETED if verified else MissionStatus.BLOCKED,
                        steps=(),
                        reason=detail if verified else f"simple_edit_delivery_unverified: {detail}",
                        qa_worker_id="simple-edit-file-verifier" if verified else None,
                    )
                    fast_done = True
        except Exception:  # noqa: BLE001 - hızlı yol isteğe bağlı
            fast_done = False

        if not fast_done:
            if claimed.objective.startswith("render:"):
                import os
                from dataclasses import replace
                from types import SimpleNamespace
                from .render_task import make_render_executor

                render_executor = make_render_executor(
                    os.environ.get("AHOS_RENDER_WORKFLOW") or str(Path(__file__).resolve().parents[2] / "workflows/ltx2_text2video.json"),
                    os.environ.get("AHOS_RENDER_OUT") or str(Path(console.runtime_dir) / "artifacts/renders"),
                )
                # A mission may have several worker steps. Render once, retaining
                # the original owner objective instead of planner-generated text.
                cached = []
                def execute_render(item, worker_id):
                    if not cached:
                        cached.append(render_executor(SimpleNamespace(
                            task_id=item.task_id, objective=claimed.objective), worker_id))
                    return replace(cached[0], task_id=item.task_id, worker_id=worker_id)
                result = console._execute(spec, claimed.objective, claimed.mission_id, executor=execute_render)
            else:
                from .scope import as_document_objective, should_document

                if should_document(claimed.objective):
                    # Karmaşık kod görevi: belge/analiz kapsamına çevrilir.
                    try:
                        from .doc_factory import make_document_factory_executor

                        doc_executor = make_document_factory_executor(Path(console.runtime_dir))
                        prior_scope = bool(getattr(console, "_scope_document", False))
                        try:
                            console._scope_document = True  # per-mission document QA
                            result = console._execute(
                                spec,
                                as_document_objective(claimed.objective),
                                claimed.mission_id,
                                executor=doc_executor,
                            )
                        finally:
                            console._scope_document = prior_scope
                        # Preserve the owner goal in the queue/audit record.
                        from dataclasses import replace as _replace
                        if getattr(result, "objective", None) != claimed.objective:
                            result = _replace(result, objective=claimed.objective)
                    except Exception as exc:  # noqa: BLE001 - fail closed, do not fake success
                        result = MissionResult(
                            mission_id=claimed.mission_id,
                            objective=claimed.objective,
                            manager_id=None,
                            status=MissionStatus.BLOCKED,
                            steps=(),
                            reason=f"doc_factory_route_failed:{type(exc).__name__}",
                        )
                else:
                    result = console._execute(spec, claimed.objective, claimed.mission_id)
        console._record(claimed.mission_id, owner, result)
        # Evidence-based feedback: score the actual *recorded* route and
        # outcome only once per mission. A queued task is not work evidence.
        try:
            from .consensus import score_plan
            from .mind_feedback import feedback as _feedback
            from .scope import should_document

            _ok = str(getattr(result.status, "value", result.status)) == "completed"
            _route = (
                "simple_edit" if fast_done else
                "render" if claimed.objective.startswith("render:") else
                "document" if should_document(claimed.objective) else "executor"
            )
            _worker = _scoring_worker(result, spec.department_id)
            _duration = max(0.0, time.monotonic() - started_at)
            recorded = _feedback(
                console.runtime_dir, _worker, spec.department_id, _ok,
                duration_s=_duration, plan_type=_route,
                mission_id=claimed.mission_id, record_plan_score=False,
            )
            # Score the same observed outcome once, after feedback's
            # per-worker mission-id deduplication gate has accepted it.
            if not (isinstance(recorded, dict) and recorded.get("duplicate")):
                score_plan(
                    console.runtime_dir, _worker, spec.department_id,
                    _route, _ok, _duration,
                )
        except Exception:  # noqa: BLE001 - scoring must not forge completion
            pass
        # Agent Atrium günlüğü: kim, hangi departmanda, ne yaptı.
        try:
            from .atrium import record as chronicle_record

            chronicle_record(
                Path(console.runtime_dir),
                f"mission.{getattr(getattr(result, 'status', None), 'value', 'done')}",
                f"{claimed.mission_id} · {claimed.primary_department} · {claimed.objective[:80]}",
            )
        except Exception:  # noqa: BLE001 - günlük isteğe bağlı
            pass
        executed.append(claimed.mission_id)
        # Başarısız görev için politika: yeniden dene (backoff) ya da CEO'ya eskalasyon.
        try:
            _handle_failure(console, claimed, result)
        except Exception:  # noqa: BLE001 - politika uygulaması akışı bozmaz
            pass

    return {"executed": executed, "blocked": blocked, "skipped": skipped}


def _failure_cause(result) -> str:
    from .failure_analytics import classify_error

    status = str(getattr(getattr(result, "status", None), "value", "") or "")
    if status in {"completed", "success"}:
        return ""
    return classify_error({"message": str(getattr(result, "reason", "") or "")})


def _handle_failure(console, claimed, result) -> None:
    """Yeniden deneme veya CEO eskalasyonu; kararı diske yazar."""

    import json
    from pathlib import Path

    from .retry_policy import decide

    cause = _failure_cause(result)
    if not cause:
        return
    attempt = int(getattr(claimed, "attempts", 0) or 0) + 1
    decision = decide(cause, attempt)
    runtime = Path(console.runtime_dir)

    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mission_id": claimed.mission_id,
        "department": claimed.primary_department,
        "cause": cause,
        "attempt": attempt,
        "retry": decision.retry,
        "delay_seconds": decision.delay_seconds,
        "escalate": decision.escalate,
        "reason": decision.reason,
    }
    path = runtime / "ceo" / "retry-policy.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    if decision.retry and console.queue is not None:
        try:
            console.queue.enqueue(
                mission_id=claimed.mission_id,
                objective=claimed.objective,
                primary_department=claimed.primary_department,
                attempts=attempt,
                max_attempts=max(2, attempt + 1),
                replace_existing=True,
            )
        except TypeError:
            # Eski imza: attempts parametresi yoksa sessizce atla.
            pass


def drain_until_empty(console, *, owner: str = "queue-drainer", max_batches: int = 20) -> dict[str, object]:
    """Bounded repeated drain (never spins forever on a failing executor)."""

    executed: list[str] = []
    blocked: list[str] = []
    for _ in range(max(1, max_batches)):
        batch = drain(console, owner=owner, limit=5)
        executed.extend(batch["executed"])  # type: ignore[arg-type]
        blocked.extend(batch["blocked"])  # type: ignore[arg-type]
        if not batch["executed"] and not batch["blocked"]:
            break
        time.sleep(0.05)
    return {"executed": executed, "blocked": blocked}
