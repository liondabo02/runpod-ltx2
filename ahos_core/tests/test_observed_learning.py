"""Verified mission scoring and grounded department conversation."""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from ahos import commune, mind_feedback, worker_mind
from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.queue_drain import drain


def test_feedback_scores_real_mission_once_and_survives_reflection(tmp_path, monkeypatch):
    monkeypatch.setattr(mind_feedback, "outcome_record",
                        lambda runtime, department, ok, duration: {"ok": ok})
    kwargs = dict(plan_type="simple_edit", duration_s=2.5, mission_id="m-1")
    first = mind_feedback.feedback(tmp_path, "software-manager", "software", True, **kwargs)
    repeated = mind_feedback.feedback(tmp_path, "software-manager", "software", True, **kwargs)
    assert first == {"ok": True}
    assert repeated["duplicate"] is True
    mind = worker_mind.load(tmp_path, "software-manager")
    score = mind.self_model["plan_scores"]["simple_edit"]
    assert score["ok"] == 1 and score["fail"] == 0 and score["total_s"] == 2.5
    worker_mind.reflect(mind)
    assert mind.self_model["plan_scores"]["simple_edit"]["ok"] == 1


def test_drain_routes_observed_status_into_plan_score(tmp_path, monkeypatch):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="m-2", objective="iş", primary_department="software")
    calls = []
    monkeypatch.setattr(mind_feedback, "feedback", lambda *args, **kw: calls.append((args, kw)))

    class Console:
        runtime_dir = tmp_path
        book = SimpleNamespace(get=lambda dep: SimpleNamespace(department_id=dep))

        def _project_for_department(self, dep):
            return None

        def _execute(self, spec, objective, mission_id, executor=None):
            return MissionResult(mission_id, objective, None, MissionStatus.COMPLETED, (),
                                 "completed", qa_worker_id="independent-qa")

        def _record(self, mission_id, owner, result):
            queue.complete(mission_id, owner=owner, result=result)

    report = drain(Console(), limit=1)
    assert report["executed"] == ["m-2"]
    assert queue.get("m-2").status is QueueStatus.COMPLETED
    assert len(calls) == 1
    args, keywords = calls[0]
    assert args[1] == "software-manager" and args[3] is True
    assert keywords["mission_id"] == "m-2"
    assert keywords["plan_type"] == "executor"
    assert keywords["duration_s"] >= 0


def test_conversation_quotes_actual_database_record_without_false_learning(tmp_path):
    db = sqlite3.connect(tmp_path / "company-service.db")
    db.execute("create table missions (mission_id text, objective text, primary_department text,"
               " status text, last_error text, updated_at text)")
    db.execute("insert into missions values (?,?,?,?,?,?)", (
        "real-block-7", "video teslimini doğrula", "creative", "blocked",
        "QA kapısı reddetti", "2026-11-05T20:00:00"))
    db.commit()
    db.close()
    departments = [{"department_id": "creative", "workers": [
        {"worker_id": "creative-manager"}, {"worker_id": "creative-specialist"}]}]
    result = commune.converse(tmp_path, departments, rounds=1, seed=42)
    messages = commune.recent(tmp_path)
    assert result["messages"] == 2
    assert len(messages) == 2
    assert all("real-block-7" in m["body"] for m in messages)
    assert any("QA kapısı reddetti" in m["body"] for m in messages)
    assert not list((tmp_path / "minds").glob("creative-*.json"))



def test_scripted_events_cannot_inflate_mission_success_rate(tmp_path):
    from ahos.worker_mind import Mind
    from ahos.strategy import apply

    mind = Mind("worker-1", "software", events=[
        {"kind": "think", "ok": True},
        {"kind": "answer", "ok": True},
        {"kind": "mission", "ok": False, "plan_type": "model"},
    ])
    assert mind.success_rate == 0.0
    mind.self_model = {"strategy": {"preferred_plan": "simple_edit"},
                       "best_plan_type": "simple_edit"}
    rating = apply(mind)
    assert rating["rate"] == 0.0
    assert rating["preferred_plan"] == "simple_edit"
    mind.events.append({"kind": "mission", "ok": True, "plan_type": "simple_edit"})
    assert mind.success_rate == 0.5
    worker_mind.reflect(mind)
    assert mind.self_model["best_plan_type"] == "simple_edit"


def test_twenty_observed_tasks_score_more_than_ten_actual_workers(tmp_path):
    """A worker is credited only when a mission result identifies that worker."""
    from ahos.mission_orchestrator import MissionStepResult, MissionStepSpec
    from ahos.workforce_execution import WorkStage

    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    for index in range(20):
        queue.enqueue(
            mission_id=f"observed-{index:02d}",
            objective=f"verify task {index}",
            primary_department="software",
        )

    class Console:
        runtime_dir = tmp_path
        book = SimpleNamespace(get=lambda department: SimpleNamespace(
            department_id=department
        ))

        def _project_for_department(self, department):
            return None

        def _execute(self, spec, objective, mission_id, executor=None):
            worker = "software-worker-" + mission_id.rsplit("-", 1)[-1]
            step = MissionStepResult(
                step=MissionStepSpec(
                    step_id="produce", title="verified production",
                    department="software", required_capabilities=frozenset(),
                ),
                stage=WorkStage.COMPLETED,
                worker_id=worker,
                worker_summary="produced tested result",
                qa_summary="independent QA passed",
                reason="completed",
                qa_worker_id="qa-01",
            )
            return MissionResult(
                mission_id, objective, "software-manager",
                MissionStatus.COMPLETED, (step,), "completed",
            )

        def _record(self, mission_id, owner, result):
            queue.complete(mission_id, owner=owner, result=result)

    report = drain(Console(), limit=20)

    assert len(report["executed"]) == 20
    scored = []
    for worker_file in (tmp_path / "minds").glob("software-worker-*.json"):
        mind = worker_mind.load(tmp_path, worker_file.stem)
        entry = mind.self_model.get("plan_scores", {}).get("executor")
        if entry:
            scored.append(entry)

    assert len(scored) > 10, f"Only {len(scored)} actual workers scored"
    assert len(scored) == 20
    assert sum(row["ok"] + row["fail"] for row in scored) == 20
    # One mission must not credit an unrelated synthetic manager as well.
    assert not (tmp_path / "minds" / "software-manager.json").exists()


def test_queue_drain_does_not_double_score_the_same_mission(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    queue.enqueue(mission_id="score-once", objective="test task",
                  primary_department="software")

    class Console:
        runtime_dir = tmp_path
        book = SimpleNamespace(get=lambda department: SimpleNamespace(
            department_id=department
        ))

        def _project_for_department(self, department):
            return None

        def _execute(self, spec, objective, mission_id, executor=None):
            return MissionResult(mission_id, objective, None,
                                 MissionStatus.COMPLETED, (), "completed",
                                 qa_worker_id="qa-01")

        def _record(self, mission_id, owner, result):
            queue.complete(mission_id, owner=owner, result=result)

    assert drain(Console(), limit=1)["executed"] == ["score-once"]
    score = worker_mind.load(tmp_path, "software-manager").self_model[
        "plan_scores"]["executor"]
    assert score["ok"] == 1 and score["fail"] == 0
