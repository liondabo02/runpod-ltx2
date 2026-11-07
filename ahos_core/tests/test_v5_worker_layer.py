"""V5 GÖREV 013/018/019 — işçi katmanı: durum, ofis eşlemesi ve kart.

Kural: kanıt yoksa işçi "boşta" sayılmaz; "çevrimdışı + kayıt yok" yazılır.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from ahos import agent_office, office_3d, worker_card, worker_state

NOW = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)


def _runtime(tmp_path, workers=(("w-a", "Alfa"), ("w-b", "Beta"))):
    payload = {"departments": [{
        "department_id": "dep", "name": "Departman",
        "workers": [{"worker_id": wid, "name": name, "role": "specialist",
                     "capabilities": ["test"]} for wid, name in workers],
    }]}
    (tmp_path / "departments.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def _metric(path, worker, at):
    row = {"worker_id": worker, "success": True, "at": at, "duration_ms": 1500}
    with (path / "worker-metrics.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_observed_step_is_working_and_carries_task(tmp_path):
    record = worker_state.derive(tmp_path, "w-a", observed_task="CMD-1", now=NOW)
    assert record["state"] == "working"
    assert record["label"] == "çalışıyor"
    assert record["source"] == "observed"
    assert record["active_task"] == "CMD-1"
    assert record["unknown"] is False


def test_fresh_recorded_event_wins_over_metrics(tmp_path):
    worker_state.set_state(tmp_path, "w-a", "blocked", note="QA reddi")
    record = worker_state.derive(tmp_path, "w-a", last_active=(NOW - timedelta(hours=1)).isoformat(),
                                 now=NOW)
    assert record["state"] == "blocked"
    assert record["source"] == "recorded"
    assert record["reason"] == "QA reddi"


def test_stale_recorded_event_falls_back_to_metrics(tmp_path):
    worker_state.set_state(tmp_path, "w-a", "blocked", note="eski olay")
    later = NOW + timedelta(hours=3)
    record = worker_state.derive(tmp_path, "w-a", last_active=later.isoformat(), now=later)
    assert record["state"] == "idle"
    assert record["source"] == "metric"


def test_recent_run_is_idle_and_old_run_is_offline(tmp_path):
    recent = worker_state.derive(tmp_path, "w-a", last_active=(NOW - timedelta(minutes=30)).isoformat(),
                                 now=NOW)
    assert recent["state"] == "idle" and recent["stale"] is False
    old = worker_state.derive(tmp_path, "w-a", last_active=(NOW - timedelta(days=2)).isoformat(),
                              now=NOW)
    assert old["state"] == "offline" and old["stale"] is True
    assert old["unknown"] is False


def test_worker_without_any_record_is_offline_not_idle(tmp_path):
    record = worker_state.derive(tmp_path, "w-yok", now=NOW)
    assert record["state"] == "offline"
    assert record["unknown"] is True
    assert record["reason"] == "çalışma kaydı yok"


def test_invalid_state_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        worker_state.set_state(tmp_path, "w-a", "uykuda")


def test_counts_cover_all_ten_states():
    result = worker_state.counts([{"state": "working"}, {"state": "working"},
                                  {"state": "idle"}, {"state": "x"}])
    assert set(result) == set(worker_state.STATES)
    assert result["working"] == 2 and result["idle"] == 1 and result["offline"] == 0


def test_roster_index_reads_real_departments(tmp_path):
    _runtime(tmp_path)
    index = agent_office.roster_index(tmp_path)
    assert index["w-a"] == {"name": "Alfa", "role": "specialist", "department": "dep"}


def test_office_snapshot_only_uses_canonical_states(tmp_path):
    _runtime(tmp_path)
    _metric(tmp_path, "w-a", (NOW - timedelta(minutes=10)).isoformat())
    snapshot = agent_office.snapshot(tmp_path)
    workers = {row["worker_id"]: row
               for dep in snapshot["departments"] for row in dep["workers"]}
    assert {row["state_code"] for row in workers.values()} <= set(worker_state.STATES)
    assert workers["w-a"]["state_code"] == "idle"
    assert workers["w-a"]["state"] == "boşta"
    assert workers["w-b"]["state_code"] == "offline"
    assert workers["w-b"]["unknown"] is True
    assert snapshot["totals"]["states"] == worker_state.counts(
        list(workers.values()), key="state_code")
    assert snapshot["totals"]["unknown_workers"] == 1


def test_worker_card_hides_private_memory_and_escapes_html(tmp_path):
    _runtime(tmp_path, workers=(("w-a", "<script>alert(1)</script>"),))
    card = worker_card.card(tmp_path, "w-a")
    assert card["private_memory_hidden"] is True
    assert "private" not in card
    page = worker_card.render_html(card)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert 'href="/intelligence"' in page


def test_worker_card_requires_a_real_worker(tmp_path):
    _runtime(tmp_path)
    assert worker_card.exists(tmp_path, "w-a") is True
    assert worker_card.exists(tmp_path, "hayalet") is False


def test_office_3d_links_worker_inspector_to_card():
    page = office_3d.render_html()
    assert 'id="workerCardLink"' in page
    assert "'/worker/'+encodeURIComponent" in page
    assert "worker.state_code" in page
