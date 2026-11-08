from __future__ import annotations

import json
from pathlib import Path

from ahos.agent_control import (
    assign_ticket,
    breaker,
    recall,
    remember,
    reset_breaker,
    ticket_for,
    ticket_key,
    ticket_prefix,
)


def test_ticket_prefix_from_project() -> None:
    assert ticket_prefix("mipiluna") == "MIP"
    assert ticket_prefix("holding-core") == "HOL"


def test_ticket_key_is_padded() -> None:
    assert ticket_key("mipiluna", 7) == "MIP-7"
    assert ticket_key("mipiluna", 0) == "MIP-1"


def test_assign_ticket_is_idempotent(tmp_path) -> None:
    first = assign_ticket(tmp_path, "CMD-1", "mipiluna")
    second = assign_ticket(tmp_path, "CMD-1", "mipiluna")

    assert first == second
    assert ticket_for(tmp_path, "CMD-1") == first


def test_assign_ticket_increments(tmp_path) -> None:
    first = assign_ticket(tmp_path, "CMD-1", "mipiluna")
    second = assign_ticket(tmp_path, "CMD-2", "mipiluna")

    assert first != second


def test_breaker_ok_on_first_failure(tmp_path) -> None:
    decision = breaker(tmp_path, "w1", success=False)

    assert decision.action == "ok" or decision.action == "steer"
    assert decision.streak == 1


def test_breaker_steers_then_constrains_then_stops(tmp_path) -> None:
    breaker(tmp_path, "w1", success=False)
    steer = breaker(tmp_path, "w1", success=False)
    constrain = breaker(tmp_path, "w1", success=False)
    stop = breaker(tmp_path, "w1", success=False)
    stopped = breaker(tmp_path, "w1", success=False)

    assert steer.action == "steer"
    assert constrain.action == "constrain"
    assert stop.action == "stop"
    assert stopped.action == "stop"


def test_breaker_resets_on_success(tmp_path) -> None:
    for _ in range(3):
        breaker(tmp_path, "w1", success=False)

    decision = breaker(tmp_path, "w1", success=True)

    assert decision.streak == 0
    assert decision.action == "ok"


def test_reset_breaker_clears_state(tmp_path) -> None:
    for _ in range(4):
        breaker(tmp_path, "w1", success=False)
    reset_breaker(tmp_path, "w1")

    assert breaker(tmp_path, "w1").action == "ok"


def test_memory_roundtrip_and_recall(tmp_path) -> None:
    remember(tmp_path, "oyun-engineering", "Seksek oyununda zorluk dengesi düzeltildi.")
    hits = recall(tmp_path, "seksek zorluk")

    assert hits
    assert hits[0]["actor"] == "oyun-engineering"


def test_recall_empty_when_no_match(tmp_path) -> None:
    remember(tmp_path, "a", "alakasız not")

    assert recall(tmp_path, "hiçgeçmeyenkelime") == []
