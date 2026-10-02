from __future__ import annotations

from ahos.holding import HoldingOperatingEngine
from ahos.opportunity import Opportunity


def _opportunity(opportunity_id: str = "opp-1") -> Opportunity:
    return Opportunity(
        opportunity_id=opportunity_id,
        title="Local software opportunity",
        source="manual",
        category="software",
        expected_value_usd=10000,
        effort=0.2,
        risk=0.1,
        confidence=0.9,
        strategic_fit=0.9,
    )


def test_end_to_end_local_holding_flow(tmp_path) -> None:
    engine = HoldingOperatingEngine(tmp_path / "holding", qualification_threshold=60)

    decision = engine.evaluate_opportunity(
        _opportunity(),
        timestamp="2026-09-16T12:00:00+00:00",
    )
    assert decision.qualified is True
    assert decision.score.score >= 60

    venture = engine.create_venture(
        venture_id="v-1",
        name="Example Venture",
        opportunity_id="opp-1",
        objectives=("build", "measure"),
        budget_ceiling_usd=2000,
        timestamp="2026-09-16T12:01:00+00:00",
    )
    assert venture.venture_id == "v-1"

    order = engine.create_work_order(
        work_order_id="wo-1",
        venture_id="v-1",
        mission_id="m-1",
        objective="Build and test reversible local software changes",
        required_capabilities=("software.build_and_test",),
        priority=10,
        budget_ceiling_usd=500,
        timestamp="2026-09-16T12:02:00+00:00",
    )
    assert order.venture_id == "v-1"
    assert order.routing_department == "software"

    snapshot = engine.venture_snapshot("v-1")
    assert snapshot.venture_id == "v-1"
    assert snapshot.entry_count == 0

    records = engine.audit.records()
    assert [r["event_type"] for r in records] == [
        "opportunity_evaluated",
        "venture_created",
        "work_order_created",
    ]
    assert engine.audit.verify_integrity() is True


def test_duplicate_opportunity_is_rejected(tmp_path) -> None:
    engine = HoldingOperatingEngine(tmp_path / "holding")
    engine.evaluate_opportunity(_opportunity())

    try:
        engine.evaluate_opportunity(_opportunity())
    except ValueError as exc:
        assert "duplicate opportunity_id" in str(exc)
    else:
        raise AssertionError("duplicate opportunity should fail")


def test_unknown_opportunity_cannot_create_venture(tmp_path) -> None:
    engine = HoldingOperatingEngine(tmp_path / "holding")

    try:
        engine.create_venture(
            venture_id="v-x",
            name="Unknown",
            opportunity_id="missing",
        )
    except KeyError as exc:
        assert "unknown opportunity_id" in str(exc)
    else:
        raise AssertionError("unknown opportunity should fail")


def test_unknown_venture_cannot_create_work_order(tmp_path) -> None:
    engine = HoldingOperatingEngine(tmp_path / "holding")

    try:
        engine.create_work_order(
            work_order_id="wo-x",
            venture_id="missing",
            mission_id="m-x",
            objective="build software",
        )
    except KeyError as exc:
        assert "unknown venture_id" in str(exc)
    else:
        raise AssertionError("unknown venture should fail")
