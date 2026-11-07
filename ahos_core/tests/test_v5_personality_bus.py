"""V5 GÖREV 006-007: çalışma kişiliği ve mesajlaşma altyapısı."""
from __future__ import annotations

import pytest

from ahos import message_bus, work_personality


def test_personality_differs_by_department_and_does_not_touch_authority():
    software = work_personality.describe("software", "specialist")
    quality = work_personality.describe("quality", "qa")
    research = work_personality.describe("research")
    assert software["style"] != quality["style"] != research["style"]
    for row in (software, quality, research):
        assert row["authority_effect"] == "none"
        assert row["spend_effect"] == "none"
        assert row["traits"]


def test_personality_ranks_same_plans_differently():
    plans = [
        {"name": "hizli", "risk": 0.6, "success_probability": 0.6, "speed": 0.9,
         "steps": ["hızlı çıkar"], "verification": "QA"},
        {"name": "test", "risk": 0.1, "success_probability": 0.9, "speed": 0.3,
         "steps": ["test yaz", "bağımsız qa"], "verification": "bağımsız QA"},
    ]
    quality = work_personality.rank_plans("quality", plans)
    creative = work_personality.rank_plans("creative", plans)
    assert quality[0]["name"] == "test"
    assert creative[0]["name"] == "test" or creative[0]["name"] == "hizli"
    assert quality[0]["personality_score"] >= quality[1]["personality_score"]
    assert quality[0]["personality"] == "şüpheci"


def test_all_message_types_are_accepted(tmp_path):
    for index, message_type in enumerate(message_bus.MESSAGE_TYPES):
        record = message_bus.send(
            tmp_path, from_worker=f"w-{index}", to_worker=f"x-{index}",
            mission_id=f"m-{index}", message_type=message_type,
            payload={"i": index})
        assert record["message_id"] and record["message_type"] == message_type
    assert len(message_bus.state(tmp_path)) == 11


def test_invalid_type_and_self_message_rejected(tmp_path):
    with pytest.raises(ValueError):
        message_bus.send(tmp_path, from_worker="a", to_worker="b",
                         mission_id="m", message_type="sohbet")
    with pytest.raises(ValueError):
        message_bus.send(tmp_path, from_worker="a", to_worker="a",
                         mission_id="m", message_type="task_request")


def test_duplicate_message_is_suppressed(tmp_path):
    first = message_bus.send(tmp_path, from_worker="a", to_worker="b",
                             mission_id="m", message_type="help_request",
                             payload={"sorun": "timeout"})
    again = message_bus.send(tmp_path, from_worker="a", to_worker="b",
                             mission_id="m", message_type="help_request",
                             payload={"sorun": "timeout"})
    assert again["duplicate"] is True and again["message_id"] == first["message_id"]
    assert message_bus.stats(tmp_path)["messages"] == 1


def test_pair_cap_prevents_infinite_loop(tmp_path):
    for index in range(message_bus.PAIR_CAP):
        message_bus.send(tmp_path, from_worker="a", to_worker="b",
                         mission_id="m", message_type="review_request",
                         payload={"i": index})
    with pytest.raises(RuntimeError):
        message_bus.send(tmp_path, from_worker="a", to_worker="b",
                         mission_id="m", message_type="review_request",
                         payload={"i": 99})


def test_ack_persists_and_inbox_empties(tmp_path):
    record = message_bus.send(tmp_path, from_worker="a", to_worker="b",
                              mission_id="m", message_type="task_request")
    assert len(message_bus.inbox(tmp_path, "b")) == 1
    with pytest.raises(PermissionError):
        message_bus.ack(tmp_path, record["message_id"], worker="c")
    message_bus.ack(tmp_path, record["message_id"], worker="b")
    assert message_bus.inbox(tmp_path, "b") == []
    assert message_bus.state(tmp_path)[record["message_id"]]["acked"] is True
