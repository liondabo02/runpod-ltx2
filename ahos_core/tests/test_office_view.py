from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ahos.office_view import build_office_model, render_office
from ahos.owner_console import build_default_console


def test_completed_mission_returns_agents_to_idle(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")

    model = build_office_model(console.book, console.queue)

    rooms = {room["department_id"]: room for room in model["rooms"]}
    creative = rooms["creative"]
    assert len(creative["workers"]) == 15
    # Bitmiş görev "çalışıyor" göstermez; ajanlar bekleme durumuna döner.
    assert model["stats"]["working"] == 0


def test_live_activity_marks_worker_as_working(tmp_path) -> None:
    from ahos.live_activity import track

    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    worker_id = console.book.require("creative").workers[0].worker_id

    with track(worker_id, "m-live", "produce", "creative"):
        model = build_office_model(console.book, console.queue)

    rooms = {room["department_id"]: room for room in model["rooms"]}
    states = {w["worker_id"]: w["state"] for w in rooms["creative"]["workers"]}
    assert states[worker_id] == "working"
    assert model["stats"]["working"] == 1


def test_office_model_returns_to_idle_after_the_window(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("yazılım şirketi kur")

    later = datetime.now(timezone.utc) + timedelta(hours=2)
    model = build_office_model(console.book, console.queue, now=later)

    assert model["stats"]["working"] == 0
    assert model["stats"]["idle"] == model["worker_count"]


def test_office_model_without_queue_is_all_idle(tmp_path) -> None:
    console = build_default_console(tmp_path)

    model = build_office_model(console.book, None)

    assert model["worker_count"] > 0
    assert model["stats"]["idle"] == model["worker_count"]
    assert model["ticker"] == []


def test_office_html_renders_rooms_and_figures(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")

    page = render_office(build_office_model(console.book, console.queue))

    assert "AHOS Ofis" in page
    assert 'class="figure' in page
    assert "Çizgi Film Stüdyosu" in page
    assert "Son hareketler" in page
    assert 'href="/"' in page


def test_office_ticker_lists_recent_work(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("yazılım şirketi kur")

    model = build_office_model(console.book, console.queue)

    assert model["ticker"]
    assert any("Yazılım" in str(item["department"]) for item in model["ticker"])
