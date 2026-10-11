from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ahos import LocalScheduler, MissionDefinition, RetryPolicy


def test_scheduler_is_dependency_safe_priority_ordered_and_repeatable() -> None:
    scheduler = LocalScheduler(
        [
            MissionDefinition("deploy", priority=100, dependencies={"prepare"}),
            MissionDefinition("report", priority=10),
            MissionDefinition("prepare", priority=1),
        ],
        RetryPolicy(max_attempts=3),
    )

    first = scheduler.schedule()
    second = scheduler.schedule()

    assert [mission.mission_id for mission in first] == ["report", "prepare"]
    assert first == second
    assert all(mission.retry.attempt == 1 for mission in first)
    assert all(mission.retry.backoff_seconds == 0.0 for mission in first)

    next_ready = scheduler.schedule(completed_ids={"prepare"})
    assert [mission.mission_id for mission in next_ready] == ["deploy", "report"]


def test_scheduler_applies_bounded_retries_and_backoff_metadata() -> None:
    scheduler = LocalScheduler(
        [MissionDefinition("work")],
        RetryPolicy(
            max_attempts=3,
            initial_backoff_seconds=2.0,
            backoff_multiplier=3.0,
            max_backoff_seconds=5.0,
        ),
    )

    assert scheduler.schedule({"other"}, {"work": 0})[0].retry.backoff_seconds == 0.0
    second = scheduler.schedule(attempts={"work": 1})[0]
    assert second.retry.attempt == 2
    assert second.retry.retries_remaining == 1
    assert second.retry.backoff_seconds == 2.0
    assert second.retry.can_retry is True

    third = scheduler.schedule(attempts={"work": 2})[0]
    assert third.retry.attempt == 3
    assert third.retry.retries_remaining == 0
    assert third.retry.backoff_seconds == 5.0
    assert third.retry.can_retry is False
    assert scheduler.schedule(attempts={"work": 3}) == []


def test_retry_policy_validation_and_metadata_are_bounded() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(initial_backoff_seconds=-1)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_multiplier=0.5)
    with pytest.raises(ValueError):
        RetryPolicy(max_backoff_seconds=float("inf"))

    policy = RetryPolicy(max_attempts=2)
    assert policy.metadata_for_attempt(1).can_retry is True
    with pytest.raises(ValueError):
        policy.backoff_seconds(2)
    with pytest.raises(ValueError):
        policy.metadata_for_attempt(3)


def test_scheduler_rejects_invalid_attempt_state_without_side_effects() -> None:
    scheduler = LocalScheduler([MissionDefinition("work")])

    with pytest.raises(KeyError):
        scheduler.schedule(attempts={"missing": 1})
    with pytest.raises(ValueError):
        scheduler.schedule(attempts={"work": -1})
    with pytest.raises(TypeError):
        scheduler.schedule(attempts={"work": True})

    assert [mission.mission_id for mission in scheduler.schedule()] == ["work"]
    with pytest.raises(FrozenInstanceError):
        scheduler.schedule()[0].retry.attempt = 2
