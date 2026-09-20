from __future__ import annotations

import json

import pytest

from ahos.venture import (
    VentureLifecycle,
    VentureRegistry,
    VentureState,
)


def test_create_and_persist_venture(tmp_path) -> None:
    registry = VentureRegistry(tmp_path / "ventures.json")
    venture = registry.create(
        venture_id="v-1",
        name="Example Venture",
        opportunity_ids=("opp-1",),
        departments=("software", "analytics"),
        objectives=("validate demand",),
        budget_ceiling_usd=5000,
        timestamp="2026-09-16T12:00:00+00:00",
    )

    assert venture.state is VentureState.IDEA
    assert venture.audit_correlation_id == "venture:v-1"

    reopened = VentureRegistry(tmp_path / "ventures.json")
    loaded = reopened.get("v-1")
    assert loaded == venture


def test_duplicate_venture_ids_are_rejected(tmp_path) -> None:
    registry = VentureRegistry(tmp_path / "ventures.json")
    registry.create(
        venture_id="v-1",
        name="One",
        timestamp="2026-09-16T12:00:00+00:00",
    )

    with pytest.raises(ValueError, match="duplicate venture_id"):
        registry.create(
            venture_id="v-1",
            name="Duplicate",
            timestamp="2026-09-16T12:01:00+00:00",
        )


def test_valid_lifecycle_transitions_are_deterministic(tmp_path) -> None:
    registry = VentureRegistry(tmp_path / "ventures.json")
    registry.create(
        venture_id="v-2",
        name="Lifecycle",
        timestamp="2026-09-16T12:00:00+00:00",
    )

    event_1 = registry.transition(
        "v-2",
        VentureState.VALIDATING,
        timestamp="2026-09-16T12:01:00+00:00",
    )
    event_2 = registry.transition(
        "v-2",
        VentureState.BUILDING,
        timestamp="2026-09-16T12:02:00+00:00",
    )
    event_3 = registry.transition(
        "v-2",
        VentureState.OPERATING,
        timestamp="2026-09-16T12:03:00+00:00",
    )

    assert event_1.from_state is VentureState.IDEA
    assert event_1.to_state is VentureState.VALIDATING
    assert event_2.to_state is VentureState.BUILDING
    assert event_3.to_state is VentureState.OPERATING
    assert registry.get("v-2").state is VentureState.OPERATING


def test_invalid_transition_is_rejected_without_mutating_registry(tmp_path) -> None:
    registry = VentureRegistry(tmp_path / "ventures.json")
    registry.create(
        venture_id="v-3",
        name="Protected",
        timestamp="2026-09-16T12:00:00+00:00",
    )

    with pytest.raises(ValueError, match="invalid venture transition"):
        registry.transition(
            "v-3",
            VentureState.OPERATING,
            timestamp="2026-09-16T12:01:00+00:00",
        )

    assert registry.get("v-3").state is VentureState.IDEA


def test_paused_venture_can_resume_and_retired_is_terminal(tmp_path) -> None:
    registry = VentureRegistry(tmp_path / "ventures.json")
    registry.create(
        venture_id="v-4",
        name="Pause Resume",
        timestamp="2026-09-16T12:00:00+00:00",
    )
    registry.transition("v-4", VentureState.VALIDATING)
    registry.transition("v-4", VentureState.PAUSED)
    registry.transition("v-4", VentureState.VALIDATING)
    registry.transition("v-4", VentureState.RETIRED)

    assert registry.get("v-4").state is VentureState.RETIRED
    assert VentureLifecycle.can_transition(
        VentureState.RETIRED,
        VentureState.IDEA,
    ) is False


def test_update_links_is_persistent_and_deduplicated(tmp_path) -> None:
    registry = VentureRegistry(tmp_path / "ventures.json")
    registry.create(
        venture_id="v-5",
        name="Links",
        timestamp="2026-09-16T12:00:00+00:00",
    )

    updated = registry.update_links(
        "v-5",
        opportunity_ids=("opp-1", "opp-1", "opp-2"),
        departments=("software", "software"),
        objectives=("build", "build", "measure"),
        budget_ceiling_usd=12000,
        timestamp="2026-09-16T12:10:00+00:00",
    )

    assert updated.opportunity_ids == ("opp-1", "opp-2")
    assert updated.departments == ("software",)
    assert updated.objectives == ("build", "measure")
    assert updated.budget_ceiling_usd == 12000

    raw = json.loads((tmp_path / "ventures.json").read_text(encoding="utf-8"))
    assert raw["v-5"]["budget_ceiling_usd"] == 12000
