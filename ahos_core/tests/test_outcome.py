"""Outcome (sonuç kaydı + kapsam ayarı) testleri — hermetik, tmp_path."""

from __future__ import annotations

from pathlib import Path

from ahos.outcome import adjust, record


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    return runtime


def test_record_writes_jsonl_and_returns_rate(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    result = record(runtime, "oyun", True, 1.5)

    assert result["samples"] == 1
    assert result["success_rate"] == 1.0
    assert (runtime / "outcome.jsonl").exists()


def test_record_rate_with_mixed_results(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    record(runtime, "oyun", False, 2.0)
    result = record(runtime, "oyun", True, 1.0)

    assert result["samples"] == 2
    assert result["success_rate"] == 0.5


def test_adjust_narrow_when_failing(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    for _ in range(3):
        record(runtime, "oyun", False, 1.0)

    decision = adjust(runtime, "oyun")

    assert decision["scope"] == "narrow"


def test_adjust_wide_when_succeeding(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    for _ in range(10):
        record(runtime, "oyun", True, 1.0)

    decision = adjust(runtime, "oyun")

    assert decision["scope"] == "wide"


def test_adjust_keep_when_empty(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    decision = adjust(runtime, "oyun")

    assert decision["scope"] == "keep"
