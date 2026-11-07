"""v2 model sheet üretimi — bağımlılık, devam ve PASS olmayan hata durumları."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def _setup(tmp_path, monkeypatch):
    import model_sheet_v2

    sheets = tmp_path / "sheets"
    sheets.mkdir()
    monkeypatch.setattr(model_sheet_v2, "SHEETS", sheets)
    monkeypatch.setattr(model_sheet_v2, "MANIFEST", tmp_path / "manifest.json")
    return model_sheet_v2, sheets


def _write(path: Path, payload: bytes = b"fake-png-bytes") -> None:
    path.write_bytes(payload)


def test_step_order_and_expression_input_is_v2_turnaround(tmp_path, monkeypatch):
    model_sheet_v2, _ = _setup(tmp_path, monkeypatch)
    ids = [step["id"] for step in model_sheet_v2.STEPS]
    assert ids == ["aden-turnaround", "aden-expressions", "kaan-turnaround", "kaan-expressions"]
    expressions = next(step for step in model_sheet_v2.STEPS if step["id"] == "kaan-expressions")
    assert expressions["input"] == "kaan-turnaround-v2-kontext-seed-503.png"
    assert expressions["depends_on"] == ["kaan-turnaround"]


def test_plan_skips_expression_until_turnaround_is_verified(tmp_path, monkeypatch):
    model_sheet_v2, sheets = _setup(tmp_path, monkeypatch)
    for step in model_sheet_v2.STEPS[:3]:
        _write(sheets / step["input"])  # girdiler var, çıktılar yok

    rows = {row["id"]: row for row in model_sheet_v2.plan({})}

    assert rows["aden-turnaround"]["action"] == "run"
    assert rows["aden-expressions"]["action"] == "skip_dependency"
    assert rows["kaan-expressions"]["action"] == "skip_dependency"


def test_verified_output_is_not_regenerated(tmp_path, monkeypatch):
    model_sheet_v2, sheets = _setup(tmp_path, monkeypatch)
    step = model_sheet_v2.STEPS[2]
    _write(sheets / step["input"])
    output = model_sheet_v2.output_path(step)
    _write(output, b"v2-turnaround")
    state = {"steps": {step["id"]: {"status": "ok", "sha256": model_sheet_v2.sha256(output)}}}

    ok, reason = model_sheet_v2.is_verified(step, state)
    outcome = model_sheet_v2.run_step(step, state)

    assert ok is True and reason == "verified"
    assert outcome["status"] == "already_done"
    assert output.read_bytes() == b"v2-turnaround"  # üzerine yazılmadı


def test_checksum_mismatch_blocks_silent_reuse(tmp_path, monkeypatch):
    model_sheet_v2, sheets = _setup(tmp_path, monkeypatch)
    step = model_sheet_v2.STEPS[0]
    output = model_sheet_v2.output_path(step)
    _write(output, b"changed-after-record")
    state = {"steps": {step["id"]: {"status": "ok", "sha256": "0" * 64}}}

    ok, reason = model_sheet_v2.is_verified(step, state)

    assert ok is False
    assert reason == "checksum_mismatch"


def test_missing_input_is_error_not_pass(tmp_path, monkeypatch):
    model_sheet_v2, _ = _setup(tmp_path, monkeypatch)
    outcome = model_sheet_v2.run_step(model_sheet_v2.STEPS[0], {})
    assert outcome["status"] == "error"
    assert outcome["reason"].startswith("input_missing")


def test_quota_error_classification():
    import model_sheet_v2

    assert model_sheet_v2.classify("You have exceeded your free ZeroGPU quota") == "zerogpu_quota"
    assert model_sheet_v2.classify("Value 432 is less than minimum value 512") == "invalid_parameter"
    assert model_sheet_v2.classify("boom") == "provider_error"


def test_quality_gate_pauses_after_aden_turnaround():
    import model_sheet_v2

    assert model_sheet_v2.pause_after("aden-turnaround", run_all=False) is True
    assert model_sheet_v2.pause_after("aden-turnaround", run_all=True) is False
    assert model_sheet_v2.pause_after("kaan-turnaround", run_all=False) is False
