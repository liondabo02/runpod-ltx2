from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ahos import atrium


def _runtime(tmp_path: Path, rows: list[tuple]) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute(
        "create table missions (mission_id text, objective text, primary_department text, "
        "status text, last_error text, updated_at text)"
    )
    con.executemany("insert into missions values (?,?,?,?,?,datetime('now'))", rows)
    con.commit()
    con.close()
    return runtime


def test_badge_for_statuses() -> None:
    assert atrium.badge_for("running") == "⌨"
    assert atrium.badge_for("completed") == "✓"
    assert atrium.badge_for("blocked", error="hata") == "!"
    assert atrium.badge_for("blocked", error="sahip onayı bekleniyor") == "?"
    assert atrium.badge_for("") == "·"


def test_needs_attention_lists_waiting_and_errors(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        [
            ("CMD-1", "onay gerekiyor", "oyun", "blocked", "sahip onayı bekleniyor"),
            ("CMD-2", "bozuk", "software", "blocked", "worker failed"),
            ("CMD-3", "çalışıyor", "oyun", "running", None),
            ("CMD-4", "bitti", "data", "completed", None),
        ],
    )

    items = atrium.needs_attention(runtime)

    badges = {item["badge"] for item in items}
    assert "?" in badges
    assert "!" in badges
    assert all(item["badge"] != "✓" for item in items)


def test_attention_counts_and_title(tmp_path) -> None:
    runtime = _runtime(
        tmp_path,
        [
            ("CMD-1", "a", "oyun", "blocked", "onay bekliyor"),
            ("CMD-2", "b", "oyun", "blocked", "hata"),
            ("CMD-3", "c", "oyun", "running", None),
        ],
    )

    counts = atrium.attention_counts(atrium.needs_attention(runtime))

    assert counts["waiting"] == 1
    assert counts["errors"] == 1
    assert "bekliyor" in atrium.title_text(counts)


def test_title_empty_when_nothing_pending() -> None:
    assert atrium.title_text({"waiting": 0, "errors": 0, "working": 0, "total": 0}) == ""


def test_chronicle_records_and_reads_newest_first(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    atrium.record(runtime, "arrival", "yeni ajan geldi")
    atrium.record(runtime, "status", "oyun çalışmaya başladı")

    events = atrium.chronicle(runtime)

    assert len(events) == 2
    assert events[0]["kind"] == "status"


def test_chronicle_is_capped(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    path = runtime / "chronicle.jsonl"
    path.write_text(
        "\n".join(json.dumps({"at": "x", "kind": "k", "detail": str(i)}) for i in range(600)) + "\n",
        encoding="utf-8",
    )

    atrium.record(runtime, "k", "yeni")

    assert len(path.read_text(encoding="utf-8").splitlines()) <= 500
