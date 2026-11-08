from __future__ import annotations

import pytest

from ahos import (
    DependencyCycleError,
    MissionDefinition,
    MissionPlanner,
    UnknownDependencyError,
)


def test_plan_is_dependency_safe_and_deterministic() -> None:
    planner = MissionPlanner(
        [
            MissionDefinition("deploy", priority=100, dependencies={"prepare"}),
            MissionDefinition("docs", priority=10),
            MissionDefinition("prepare", priority=1),
            MissionDefinition("release", priority=10),
        ]
    )

    assert planner.plan() == ["docs", "release", "prepare", "deploy"]
    assert planner.plan() == ["docs", "release", "prepare", "deploy"]


def test_readiness_uses_completed_dependencies_and_priority() -> None:
    planner = MissionPlanner(
        [
            MissionDefinition("prepare", priority=1),
            MissionDefinition("deploy", priority=20, dependencies={"prepare"}),
            MissionDefinition("report", priority=10),
        ]
    )

    assert [mission.mission_id for mission in planner.ready_missions()] == [
        "report",
        "prepare",
    ]
    assert planner.is_ready("deploy") is False
    assert [mission.mission_id for mission in planner.ready_missions({"prepare"})] == [
        "deploy",
        "report",
    ]
    assert planner.is_ready("deploy", {"prepare"}) is True
    assert planner.plan({"prepare"}) == ["deploy", "report"]


def test_unknown_dependencies_are_rejected() -> None:
    with pytest.raises(UnknownDependencyError, match="unknown mission 'missing'"):
        MissionPlanner([MissionDefinition("work", dependencies={"missing"})])


def test_dependency_cycles_are_rejected_with_deterministic_path() -> None:
    with pytest.raises(DependencyCycleError) as error:
        MissionPlanner(
            [
                MissionDefinition("alpha", dependencies={"beta"}),
                MissionDefinition("beta", dependencies={"alpha"}),
            ]
        )

    assert error.value.cycle == ("alpha", "beta", "alpha")
