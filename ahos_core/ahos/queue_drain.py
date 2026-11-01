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
            if project is not None:
                from .simple_edits import apply_simple_edit, parse_simple_edit

                project_root = project.work_path or project.path
                edit = parse_simple_edit(project_root, claimed.objective)
                if edit is not None:
                    ok, detail = apply_simple_edit(project_root, edit)
                    result = MissionResult(
                        mission_id=claimed.mission_id,
                        objective=claimed.objective,
                        manager_id=None,
                        status=MissionStatus.COMPLETED if ok else MissionStatus.BLOCKED,
                        steps=(),
                        reason=detail,
                    )
                    fast_done = True
        except Exception:  # noqa: BLE001 - hızlı yol isteğe bağlı
            fast_done = False

        if not fast_done:
            result = console._execute(spec, claimed.objective, claimed.mission_id)
        console._record(claimed.mission_id, owner, result)
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
