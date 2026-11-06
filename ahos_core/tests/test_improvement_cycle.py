from __future__ import annotations

from ahos.improvement_cycle import CycleResult, OBJECTIVES, run_cycle


class FakeMission:
    def __init__(self, department: str) -> None:
        self.primary_department = department


class FakeQueue:
    def __init__(self, pending: list[str] | None = None) -> None:
        self.pending = [FakeMission(d) for d in (pending or [])]
        self.enqueued: list[dict] = []

    def list(self, statuses=None, **kwargs):
        return tuple(self.pending)

    def enqueue(self, **kwargs):
        self.enqueued.append(kwargs)
        return kwargs


def test_creates_tasks_for_idle_departments() -> None:
    queue = FakeQueue()
    result = run_cycle(queue, ["data", "finance"], limit=4, stamp="20260101120000")

    assert len(result.created) == 2
    assert all(mission_id.startswith("CMD-") for mission_id in result.created)
    assert len(queue.enqueued) == 2


def test_skips_departments_with_pending_work() -> None:
    queue = FakeQueue(pending=["data"])
    result = run_cycle(queue, ["data", "finance"], limit=4, stamp="20260101120000")

    assert "data" in result.skipped
    assert len(result.created) == 1
    assert queue.enqueued[0]["primary_department"] == "finance"


def test_respects_limit() -> None:
    queue = FakeQueue()
    result = run_cycle(queue, ["data", "finance", "quality", "research"], limit=2, stamp="x1")

    assert len(result.created) == 2


def test_unknown_department_is_skipped() -> None:
    queue = FakeQueue()
    result = run_cycle(queue, ["bilinmeyen"], limit=2, stamp="x2")

    assert result.created == ()
    assert result.skipped == ("bilinmeyen",)


def test_every_department_has_objectives() -> None:
    expected = {
        "oyun", "creative", "software", "data", "finance", "guvenlik",
        "quality", "research", "marketing", "sales", "support", "operations",
        "infrastructure", "holding",
    }
    assert expected.issubset(set(OBJECTIVES))
    assert all(len(options) >= 2 for options in OBJECTIVES.values())
