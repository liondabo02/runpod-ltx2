from __future__ import annotations

import json
from pathlib import Path

from ahos.cost_report import build_report


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "model-spend.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_missing_ledger_is_zero_cost(tmp_path) -> None:
    report = build_report(tmp_path / "yok.jsonl")

    assert report.calls == 0
    assert report.usd == 0.0
    assert "ücretli kullanım: HAYIR" in report.summary()


def test_free_model_calls_are_counted_without_paid_flag(tmp_path) -> None:
    ledger = _ledger(
        tmp_path,
        [
            {"model": "qwen2.5-coder:7b", "usd": 0.0},
            {"model": "qwen2.5-coder:3b", "usd": 0.0},
        ],
    )

    report = build_report(ledger)

    assert report.calls == 2
    assert report.usd == 0.0
    assert report.free_calls == 2
    assert report.paid_models == []


def test_paid_calls_are_flagged(tmp_path) -> None:
    ledger = _ledger(
        tmp_path,
        [
            {"model": "qwen2.5-coder:7b", "usd": 0.0},
            {"model": "openai/gpt-4o-mini", "usd": 0.001875},
        ],
    )

    report = build_report(ledger)

    assert report.calls == 2
    assert round(report.usd, 6) == 0.001875
    assert report.paid_models == ["openai/gpt-4o-mini"]
    assert "ücretli kullanım: EVET" in report.summary()


def test_broken_lines_are_ignored(tmp_path) -> None:
    path = tmp_path / "model-spend.jsonl"
    path.write_text('{"model":"qwen","usd":0}\nbozuk satır\n', encoding="utf-8")

    report = build_report(path)

    assert report.calls == 1
