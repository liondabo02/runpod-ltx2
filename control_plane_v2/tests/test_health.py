from __future__ import annotations

import json
import time

import pytest

from miniverse.health import check_heartbeat, write_heartbeat


def test_health_roundtrip(tmp_path):
    path = tmp_path / "heartbeat.json"
    write_heartbeat(path, owner="worker-1", state="polling")
    payload = check_heartbeat(path, max_age_seconds=5)
    assert payload["owner"] == "worker-1"
    assert payload["state"] == "polling"
    assert float(payload["age_seconds"]) >= 0


def test_stale_health_fails(tmp_path):
    path = tmp_path / "heartbeat.json"
    path.write_text(
        json.dumps({"owner": "worker-1", "state": "polling", "timestamp": time.time() - 100}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="stale"):
        check_heartbeat(path, max_age_seconds=5)
