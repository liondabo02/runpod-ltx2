"""Worker brains and the live office viewer."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from ahos import brain, office
from ahos.office_server import serve


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "departments.json").write_text(
        json.dumps(
            {
                "version": 1,
                "departments": [
                    {
                        "department_id": "oyun",
                        "name": "Oyun Geliştirme",
                        "mission": "çocuk oyunları",
                        "capabilities": ["game_design"],
                        "workers": [
                            {
                                "worker_id": "oyun-manager",
                                "name": "Müdür",
                                "role": "department_manager",
                                "team_id": "oyun-leadership",
                                "capabilities": ["planning"],
                            },
                            {
                                "worker_id": "oyun-dev",
                                "name": "Geliştirici",
                                "role": "software_engineer",
                                "team_id": "oyun",
                                "capabilities": ["javascript"],
                                "reports_to": "oyun-manager",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (runtime / "daemon-state.json").write_text(
        json.dumps({"status": "running", "executor_mode": "model"}), encoding="utf-8"
    )
    (runtime / "daemon-missions.jsonl").write_text(
        json.dumps({"status": "routed", "changed_files": 2}) + "\n", encoding="utf-8"
    )
    return runtime


def test_brain_is_append_only(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    brain.remember(runtime, "oyun-dev", "proje 133 dosya")
    brain.remember(runtime, "oyun-dev", "kabul kapısı yeşil")
    brain.think(runtime, "oyun-dev", "sıradaki işi alıyorum", mood="focused")
    brain.add_idea(runtime, "oyun-dev", "precache'i genişletelim")

    loaded = brain.load(runtime, "oyun-dev")
    assert len(loaded["memories"]) == 2
    assert loaded["thoughts"][-1]["text"].startswith("sıradaki")
    assert loaded["ideas"][-1]["text"].startswith("precache")
    assert loaded.get("mood") == "focused"


def test_reflect_produces_a_grounded_thought(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    result = brain.reflect(
        runtime,
        "oyun-dev",
        {"role": "engineer", "pending": 3, "failures": 0, "delivered": 1, "last_task": "kart ekle"},
    )

    assert result["thoughts"][-1]["text"]
    assert "3" in result["thoughts"][-1]["text"]


def test_office_rooms_and_workers(tmp_path) -> None:
    state = office.build(_runtime(tmp_path))

    assert state["holding"]["daemon"] == "running"
    assert len(state["rooms"]) == 1
    room = state["rooms"][0]
    assert room["id"] == "oyun"
    assert {worker["id"] for worker in room["workers"]} == {"oyun-manager", "oyun-dev"}
    assert all(worker["avatar"] for worker in room["workers"])


def test_office_server_serves_state_and_accepts_an_idea(tmp_path) -> None:
    from types import SimpleNamespace

    runtime = _runtime(tmp_path)

    class FakeConsole:
        def route(self, text):
            return SimpleNamespace(department_id="oyun", name="Oyun Geliştirme"), 9

        def _create_for_task(self, text):  # pragma: no cover - route always hits
            raise AssertionError("departman zaten var")

    server: ThreadingHTTPServer = serve(runtime, port=0, console=FakeConsole())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/api/office", timeout=10) as response:
            state = json.loads(response.read().decode("utf-8"))
        assert state["rooms"]

        request = urllib.request.Request(
            f"{base}/api/idea",
            data=json.dumps({"text": "çocuklar için yeni bir oyun yapmak istiyorum"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        assert result["ok"] is True
        assert result["tasks"] == 3
        assert list((runtime / "ideas").glob("*.json")), "fikir diske yazılmalı"
    finally:
        server.shutdown()
        server.server_close()
