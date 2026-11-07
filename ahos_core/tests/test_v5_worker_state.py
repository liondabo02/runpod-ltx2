"""V5 GÖREV 013: işçi durum makinesi."""
from __future__ import annotations

import pytest

from ahos import worker_state


def test_ten_states_defined():
    assert len(worker_state.STATES) == 10
    assert "learning" in worker_state.STATES and "offline" in worker_state.STATES


def test_event_derivation_and_restart(tmp_path):
    worker_state.derive_from_event(tmp_path, "w-1", event="mission")
    worker_state.derive_from_event(tmp_path, "w-2", event="learning", note="ders")
    worker_state.derive_from_event(tmp_path, "w-3", event="mission", ok=False)
    assert worker_state.get_state(tmp_path, "w-1")["state"] == "working"
    assert worker_state.get_state(tmp_path, "w-2")["state"] == "learning"
    assert worker_state.get_state(tmp_path, "w-3")["state"] == "blocked"
    assert len(worker_state.all_states(tmp_path)) == 3


def test_learning_is_not_production_and_invalid_rejected(tmp_path):
    worker_state.set_state(tmp_path, "w-1", "learning")
    row = worker_state.get_state(tmp_path, "w-1")
    assert row["state"] == "learning" and row["state"] != "working"
    with pytest.raises(ValueError):
        worker_state.set_state(tmp_path, "w-1", "uretim")


def test_unknown_worker_is_offline_without_record(tmp_path):
    assert worker_state.get_state(tmp_path, "yok")["state"] == "offline"
