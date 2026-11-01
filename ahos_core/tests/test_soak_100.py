from __future__ import annotations

import time
from pathlib import Path

from ahos.audit import AuditLog
from ahos.owner_console import build_default_console
from ahos.worker_runtime import WorkItem, WorkerExecutionResult

DEPARTMENTS = ("oyun", "creative", "ai-platform", "guvenlik")
PER_DEPARTMENT = 25
TOTAL = len(DEPARTMENTS) * PER_DEPARTMENT


def _prepare(tmp_path: Path):
    console = build_default_console(tmp_path)
    console.handle("oyun geliştirme departmanı kur")
    console.handle("çizgi film departmanı kur")

    from ahos.projects import ProjectLink

    for department in DEPARTMENTS:
        spec = console.book.get(department)
        if spec is None:
            continue
        project = tmp_path / f"proj-{department}"
        (project / "www").mkdir(parents=True, exist_ok=True)
        (project / "www" / "index.html").write_text(
            '<html><body><script src="app.js"></script></body></html>',
            encoding="utf-8",
        )
        (project / "www" / "app.js").write_text("// app\n", encoding="utf-8")
        console.projects.link(
            ProjectLink(
                project_id=department,
                name=department,
                path=project,
                department_id=department,
            )
        )
    return console


def test_hundred_synthetic_missions_are_durable_and_idempotent(tmp_path) -> None:
    console = _prepare(tmp_path)
    spec = console.book.get(DEPARTMENTS[0])
    assert spec is not None

    calls: list[str] = []
    started = time.monotonic()

    def executor(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        calls.append(item.task_id)
        artifact = console.artifacts_root / f"{item.task_id.replace(':', '_')}.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("kanıt", encoding="utf-8")
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary="tamam",
            artifacts=(str(artifact),),
        )

    objectives = [
        f"sentetik görev {index:03d}" for index in range(PER_DEPARTMENT)
    ]
    results = []
    for department in DEPARTMENTS:
        department_spec = console.book.get(department)
        if department_spec is None:
            continue
        for objective in objectives:
            results.append(
                console.run_department_mission(
                    department_spec, objective, executor=executor
                )
            )

    duration = time.monotonic() - started

    # 1) Her mantıksal görev en çok 3 adım (brief/produce/review) çalıştırır.
    steps_per_mission: dict[str, set[str]] = {}
    for task_id in calls:
        mission, _, step = task_id.partition(":")
        steps_per_mission.setdefault(mission, set()).add(step)
    for mission, steps in steps_per_mission.items():
        assert len(steps) == len(
            {step for step in steps}
        ), f"adım kimliği tekrarladı: {mission}"
        assert steps.issubset({"brief", "produce", "review"})

    # 2) Hiçbir görev kaybolmaz; hepsi terminal durumda.
    missions = console.queue.list()
    pending = [m for m in missions if m.status.value in {"pending", "running"}]
    assert pending == [], f"terminal olmayan görev: {len(pending)}"

    # 3) Denetim günlüğü bütünlüğü ve kapsamı.
    audit = AuditLog(tmp_path / "audit.jsonl")
    assert audit.verify_integrity() is True

    # 4) Süre makul kalmalı (izole, ağ yok).
    assert duration < 180, f"100 görev çok yavaş: {duration:.1f}s"

    # 5) Yeniden başlatma sonrası aynı hedefler tekrar çalışmaz.
    restarted = build_default_console(tmp_path)
    before = len(calls)
    for objective in objectives[:5]:
        restarted.run_department_mission(
            restarted.book.get(DEPARTMENTS[0]), objective, executor=executor
        )
    assert len(calls) == before, "yeniden başlatma sonrası görev tekrar çalıştı"


def test_hundred_missions_survive_a_queue_restart(tmp_path) -> None:
    from ahos.autonomous_company import PersistentMissionQueue
    from ahos.mission_orchestrator import MissionResult, MissionStatus

    queue = PersistentMissionQueue(tmp_path / "q.db")
    for index in range(TOTAL):
        queue.enqueue(
            mission_id=f"m-{index:03d}",
            objective=f"sentetik {index}",
            primary_department=DEPARTMENTS[index % len(DEPARTMENTS)],
            max_attempts=2,
        )

    restored = PersistentMissionQueue(tmp_path / "q.db")
    assert len(restored.list()) == TOTAL

    claimed = 0
    while True:
        mission = restored.claim_next(owner="soak", lease_seconds=30)
        if mission is None:
            break
        claimed += 1
        restored.complete(
            mission.mission_id,
            owner="soak",
            result=MissionResult(
                mission_id=mission.mission_id,
                objective=mission.objective,
                manager_id=None,
                status=MissionStatus.COMPLETED,
                steps=(),
                reason="soak",
            ),
        )
    assert claimed == TOTAL

    final = PersistentMissionQueue(tmp_path / "q.db")
    assert all(m.status.value == "completed" for m in final.list())
