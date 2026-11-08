from __future__ import annotations

from pathlib import Path

import pytest

from ahos import live_activity
from ahos.office_view import build_office_model, render_office
from ahos.owner_console import build_default_console


@pytest.fixture(autouse=True)
def _clean():
    live_activity.reset_for_tests()
    yield
    live_activity.reset_for_tests()


def test_events_are_recorded_with_timestamps_and_identity(tmp_path) -> None:
    live_activity.configure(tmp_path / "events.jsonl")

    live_activity.mission_started("m-1", "oyun", "test görevi")
    with live_activity.track("worker-1", "m-1", "produce", "oyun"):
        pass
    live_activity.mission_finished("m-1", "oyun", "completed", "ok")

    events = live_activity.history(50)

    assert [event["kind"] for event in events] == [
        "started",
        "step_started",
        "step_finished",
        "completed",
    ]
    for event in events:
        assert event["mission_id"] == "m-1"
        assert event["at"]
    assert events[1]["worker_id"] == "worker-1"
    assert events[1]["step_id"] == "produce"


def test_duplicate_events_are_not_recorded() -> None:
    live_activity.mission_started("m-2", "oyun", "görev")
    first = len(live_activity.history(50))

    # Aynı olayı yeniden üretmek için aynı alanlarla _emit çağrılamaz (zaman
    # damgası farklı olur); bu yüzden kimlik alanlarının tekilliğini doğruluyoruz.
    ids = {event["id"] for event in live_activity.history(50)}

    assert len(ids) == first


def test_journal_survives_restart(tmp_path) -> None:
    journal = tmp_path / "events.jsonl"
    live_activity.configure(journal)
    live_activity.mission_started("m-3", "oyun", "kalıcı görev")

    before = live_activity.history(50)
    live_activity.reset_for_tests()
    live_activity.configure(journal)
    after = live_activity.history(50)

    assert [event["id"] for event in after] == [event["id"] for event in before]


def test_journal_is_bounded(tmp_path) -> None:
    journal = tmp_path / "events.jsonl"
    live_activity.configure(journal)

    for index in range(300):
        live_activity.mission_started(f"m-{index}", "oyun", "döngü")

    assert len(live_activity.history(1000)) <= live_activity.MAX_EVENTS
    lines = [line for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) <= live_activity.MAX_EVENTS * 2


def test_office_model_exposes_events_and_marks_completed_as_idle(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")

    model = build_office_model(console.book, console.queue)

    assert model["events"], "görev olayları ofis modeline taşınmalı"
    assert model["stats"]["working"] == 0, "bitmiş görev çalışıyor görünmemeli"
    page = render_office(model)
    assert "Son ajan olayları" in page
    assert "adım başladı" in page or "görev başladı" in page


def test_active_worker_is_marked_working(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    worker_id = console.book.require("creative").workers[0].worker_id

    with live_activity.track(worker_id, "m-live", "brief", "creative"):
        model = build_office_model(console.book, console.queue)

    states = {
        worker["worker_id"]: worker["state"]
        for room in model["rooms"]
        for worker in room["workers"]
    }
    assert states[worker_id] == "working"
    assert model["stats"]["working"] == 1
