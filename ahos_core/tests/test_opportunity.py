from __future__ import annotations

import pytest

from ahos.opportunity import (
    Opportunity,
    OpportunityScorer,
    OpportunityStatus,
    OpportunityStore,
)


def _opportunity(
    opportunity_id: str,
    *,
    expected_value_usd: float = 5_000,
    effort: float = 0.3,
    risk: float = 0.2,
    confidence: float = 0.8,
    strategic_fit: float = 0.9,
) -> Opportunity:
    return Opportunity(
        opportunity_id=opportunity_id,
        title=f"Opportunity {opportunity_id}",
        source="local-test",
        category="software",
        expected_value_usd=expected_value_usd,
        effort=effort,
        risk=risk,
        confidence=confidence,
        strategic_fit=strategic_fit,
    )


def test_score_is_deterministic_and_bounded() -> None:
    scorer = OpportunityScorer(expected_value_reference_usd=10_000)
    item = _opportunity("opp-1")

    first = scorer.score(item)
    second = scorer.score(item)

    assert first == second
    assert 0 <= first.score <= 100


def test_better_value_lower_effort_and_risk_scores_higher() -> None:
    scorer = OpportunityScorer()

    strong = _opportunity(
        "strong",
        expected_value_usd=10_000,
        effort=0.1,
        risk=0.1,
        confidence=0.9,
        strategic_fit=0.9,
    )
    weak = _opportunity(
        "weak",
        expected_value_usd=1_000,
        effort=0.9,
        risk=0.9,
        confidence=0.3,
        strategic_fit=0.2,
    )

    assert scorer.score(strong).score > scorer.score(weak).score


def test_ranking_is_stable_for_ties() -> None:
    scorer = OpportunityScorer()
    ranked = scorer.rank((_opportunity("b"), _opportunity("a")))

    assert [item.opportunity_id for item in ranked] == ["a", "b"]


def test_local_store_round_trip_and_duplicate_protection(tmp_path) -> None:
    path = tmp_path / "opportunities.jsonl"
    store = OpportunityStore(path)
    item = _opportunity("opp-2")

    stored = store.append(item, timestamp="2026-09-16T12:00:00+00:00")

    assert stored.created_at == "2026-09-16T12:00:00+00:00"
    loaded = store.get("opp-2")
    assert loaded is not None
    assert loaded.status is OpportunityStatus.NEW
    assert loaded.expected_value_usd == 5_000

    with pytest.raises(ValueError, match="duplicate opportunity_id"):
        store.append(item)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("effort", -0.1),
        ("effort", 1.1),
        ("risk", -0.1),
        ("confidence", 1.1),
        ("strategic_fit", -0.1),
    ],
)
def test_normalized_fields_must_be_between_zero_and_one(field, value) -> None:
    kwargs = {
        "expected_value_usd": 1_000,
        "effort": 0.5,
        "risk": 0.5,
        "confidence": 0.5,
        "strategic_fit": 0.5,
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        _opportunity("invalid", **kwargs)
