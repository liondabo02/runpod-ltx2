from __future__ import annotations

import sqlite3

import pytest

from ahos import Mission, MissionStateStore, MissionStatus


def test_create_and_read_mission_persistently(tmp_path) -> None:
    database = tmp_path / "missions.db"
    created = MissionStateStore(database).create_mission("mission-1")

    assert created == Mission(
        mission_id="mission-1",
        status=MissionStatus.PENDING,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )

    reopened = MissionStateStore(database)
    assert reopened.read_mission("mission-1") == created
    assert reopened.read_mission("missing") is None


def test_update_mission_changes_status_without_changing_creation_time(tmp_path) -> None:
    store = MissionStateStore(tmp_path / "missions.db")
    created = store.create_mission("mission-1", MissionStatus.RUNNING)

    updated = store.update_mission("mission-1", MissionStatus.COMPLETED)

    assert updated is not None
    assert updated.mission_id == "mission-1"
    assert updated.status is MissionStatus.COMPLETED
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at
    assert store.update_mission("missing", MissionStatus.FAILED) is None


def test_status_values_are_typed_and_invalid_values_are_rejected(tmp_path) -> None:
    store = MissionStateStore(tmp_path / "missions.db")

    created = store.create_mission("mission-1", "failed")

    assert created.status is MissionStatus.FAILED
    with pytest.raises(ValueError):
        store.update_mission("mission-1", "unknown")


def test_schema_creation_is_migration_safe(tmp_path) -> None:
    database = tmp_path / "missions.db"
    first = MissionStateStore(database)
    first.create_mission("mission-1", MissionStatus.CANCELLED)

    second = MissionStateStore(database)

    assert second.read_mission("mission-1") is not None
    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(missions)")
        }
    assert columns == {"mission_id", "status", "created_at", "updated_at"}
