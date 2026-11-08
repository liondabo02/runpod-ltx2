"""Bounds, dedupe, timeout and fallback behaviour of the cloud worker.

The cloud worker runs while the PC is off, so every loop it owns must be
bounded: tasks per run, task-list growth, wall-clock budget and model attempts.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER_PATH = ROOT / "ops" / "cloud" / "cloud_worker.py"


def _load(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("cloud_worker_test", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    project = tmp_path / "project"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{"department": "oyun", "title": "Bir şey ekle"}]), encoding="utf-8")
    outbox = tmp_path / "outbox"
    outbox.mkdir()

    monkeypatch.setattr(module, "PROJECT", project)
    monkeypatch.setattr(module, "TASKS", tasks)
    monkeypatch.setattr(module, "OUTBOX", outbox)
    monkeypatch.setattr(module, "STOP_FILE", tmp_path / "STOP")
    monkeypatch.setattr(module, "KEY", "test-key")
    monkeypatch.setattr(module, "MODELS", ["a:free", "b:free"])
    monkeypatch.setattr(module, "MAX_TASKS_PER_RUN", 1)
    monkeypatch.setattr(module, "MAX_TASKS_IN_LIST", 10)
    monkeypatch.setattr(module, "RUN_BUDGET_SECONDS", 60)
    return module, tmp_path


def _valid_raw() -> str:
    return json.dumps(
        {
            "summary": "eklendi",
            "edits": [{"path": "www/index.html", "find": "<html>", "replace": "<html lang='tr'>"}],
        }
    )


def test_stop_file_blocks_all_production(monkeypatch, tmp_path, capsys) -> None:
    module, _ = _load(monkeypatch, tmp_path)
    module.STOP_FILE.write_text("dur", encoding="utf-8")
    called: list[str] = []
    monkeypatch.setattr(module, "call_model", lambda *a, **k: called.append("x") or ("m", _valid_raw()))

    assert module.main() == 0
    assert called == [], "acil durdurma açıkken model çağrılmamalı"
    assert list(module.OUTBOX.glob("*.json")) == []


def test_one_run_produces_at_most_the_cap(monkeypatch, tmp_path) -> None:
    module, _ = _load(monkeypatch, tmp_path)
    module.TASKS.write_text(
        json.dumps(
            [
                {"department": "oyun", "title": "Birinci görev ekle"},
                {"department": "oyun", "title": "İkinci görev ekle"},
                {"department": "oyun", "title": "Üçüncü görev ekle"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "call_model", lambda *a, **k: ("m:free", _valid_raw()))

    assert module.main() == 0
    assert len(list(module.OUTBOX.glob("*.json"))) == 1


def test_existing_proposal_is_not_regenerated(monkeypatch, tmp_path) -> None:
    module, _ = _load(monkeypatch, tmp_path)
    title = "Bir şey ekle"
    digest = module.hashlib.sha256(f"oyun|{title}".encode()).hexdigest()[:16]
    (module.OUTBOX / f"{digest}.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        module, "call_model", lambda task, **k: calls.append(task) or ("m", _valid_raw())
    )

    assert module.main() == 0
    assert calls == [], "aynı görev için ikinci kez model çağrılmamalı"


def test_run_budget_stops_the_loop(monkeypatch, tmp_path) -> None:
    module, _ = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "RUN_BUDGET_SECONDS", -1)
    monkeypatch.setattr(module, "call_model", lambda *a, **k: ("m", _valid_raw()))

    assert module.main() == 0
    assert list(module.OUTBOX.glob("*.json")) == []


def test_web_only_scope_rejects_native_paths(monkeypatch, tmp_path) -> None:
    module, _ = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "PROJECT", tmp_path / "project")
    payload = {
        "edits": [
            {"path": "android/app/src/main/MainActivity.java", "find": "a", "replace": "b"},
            {"path": "www/index.html", "find": "<html>", "replace": "<html lang='tr'>"},
        ]
    }

    edits = module.validate(payload)

    assert [edit["path"] for edit in edits] == ["www/index.html"], "android hedefi reddedilmeli"


def test_fallback_tries_each_model_once_then_local(monkeypatch, tmp_path) -> None:
    module, _ = _load(monkeypatch, tmp_path)
    attempts: list[str] = []

    def fake_urlopen(request, timeout=None):
        payload = json.loads(request.data.decode("utf-8"))
        attempts.append(payload["model"])
        raise HTTPError("https://x", 429, "Too Many Requests", None, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError):
        module._chat("sys", "prompt")

    assert attempts == ["a:free", "b:free", module.LOCAL_MODEL], "sınırlı fallback"
