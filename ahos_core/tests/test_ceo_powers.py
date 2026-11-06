from __future__ import annotations

import json
from pathlib import Path

from ahos import ceo_powers


def _spend(runtime: Path, cost: float, day: str | None = None) -> None:
    day = day or ceo_powers.time.strftime("%Y-%m-%d")
    with (runtime / "premium-spend.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"day": day, "cost_usd": cost}) + "\n")


def test_can_spend_within_default_cap(tmp_path) -> None:
    ok, reason = ceo_powers.can_spend(tmp_path, "oyun", 0.01)

    assert ok is True
    assert reason == ""


def test_can_spend_blocks_when_cap_reached(tmp_path) -> None:
    ceo_powers.set_cap(tmp_path, "oyun", 0.05)
    _spend(tmp_path, 0.05)

    ok, reason = ceo_powers.can_spend(tmp_path, "oyun", 0.01)

    assert ok is False
    assert "bütçe dolu" in reason


def test_set_cap_and_caps_roundtrip(tmp_path) -> None:
    ceo_powers.set_cap(tmp_path, "software", 1.25)

    assert ceo_powers.caps(tmp_path)["software"] == 1.25


def test_spent_today_ignores_old_days(tmp_path) -> None:
    _spend(tmp_path, 9.0, day="2000-01-01")
    _spend(tmp_path, 0.02)

    assert ceo_powers.spent_today(tmp_path) == 0.02


def test_summary_reports_caps(tmp_path) -> None:
    ceo_powers.set_cap(tmp_path, "data", 0.2)

    payload = ceo_powers.summary(tmp_path)

    assert payload["caps"]["data"] == 0.2
    assert "spent_today_usd" in payload


def _retry_records(runtime: Path, cause: str, count: int, department: str = "oyun") -> None:
    path = runtime / "ceo" / "retry-policy.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for _ in range(count):
            handle.write(json.dumps({"cause": cause, "department": department}) + "\n")


def test_detect_crisis_none_below_threshold(tmp_path) -> None:
    _retry_records(tmp_path, "worker_failed", 2)

    assert ceo_powers.detect_crisis(tmp_path) is None


def test_detect_crisis_at_threshold(tmp_path) -> None:
    _retry_records(tmp_path, "worker_failed", 3)

    crisis = ceo_powers.detect_crisis(tmp_path)

    assert crisis is not None
    assert crisis.cause == "worker_failed"
    assert "oyun" in crisis.departments


def test_act_records_escalation(tmp_path) -> None:
    _retry_records(tmp_path, "model_unavailable", 3)

    payload = ceo_powers.act(tmp_path)

    assert payload["crisis"] is not None
    assert (tmp_path / "ceo" / "escalations.jsonl").exists()


def test_act_without_crisis_is_noop(tmp_path) -> None:
    assert ceo_powers.act(tmp_path)["crisis"] is None



def test_crisis_does_not_enqueue_duplicate_unresolved_missions(tmp_path) -> None:
    from ahos.autonomous_company import PersistentMissionQueue

    _retry_records(tmp_path, "acceptance_failed", 4, department="creative")
    first = ceo_powers.act(tmp_path)
    assert first["crisis"] is not None
    assert len(first["crisis"]["missions"]) == 1

    second = ceo_powers.act(tmp_path)
    assert second["crisis"]["missions"] == []
    assert second["crisis"]["skipped_duplicate_departments"] == ["creative"]
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    crisis = [m for m in queue.list() if m.objective.startswith("KRİZ GÖREVİ:")]
    assert len(crisis) == 1



def test_crisis_retries_of_one_mission_count_only_once(tmp_path) -> None:
    path = tmp_path / "ceo" / "retry-policy.jsonl"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8") as handle:
        for _ in range(6):
            handle.write(json.dumps({"cause": "acceptance_failed",
                                     "department": "creative", "mission_id": "same-1"}) + "\n")
    assert ceo_powers.detect_crisis(tmp_path, threshold=3) is None
    with path.open("a", encoding="utf-8") as handle:
        for mission in ("other-2", "other-3"):
            handle.write(json.dumps({"cause": "acceptance_failed",
                                     "department": "creative", "mission_id": mission}) + "\n")
    result = ceo_powers.detect_crisis(tmp_path, threshold=3)
    assert result is not None and result.count == 3
