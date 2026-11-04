"""learning_feedback testleri (hermetik: tmp_path kullanır)."""

from __future__ import annotations

from pathlib import Path

from ahos.learning_feedback import apply_to_prompt, top_cards, weights


def test_weights_creates_dict(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    result = weights(runtime, [{"id": "card-1", "passed": 4, "total": 5}])

    assert result["card-1"]["wins"] == 4
    assert result["card-1"]["losses"] == 1
    assert (runtime / "learning" / "weights.json").exists()


def test_top_cards_returns_sorted(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    weights(
        runtime,
        [
            {"id": "low", "passed": 1, "total": 4},
            {"id": "high", "passed": 4, "total": 4},
        ],
    )

    cards = top_cards(runtime, n=2)

    assert [card["id"] for card in cards] == ["high", "low"]


def test_top_cards_empty_when_no_weights(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    assert top_cards(runtime, n=3) == []


def test_apply_to_prompt_enriches(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    weights(runtime, [{"id": "ders-1", "passed": 3, "total": 4}])

    enriched = apply_to_prompt(runtime, "TEMEL İSTEM")

    assert "TEMEL İSTEM" in enriched
    assert "### Öğrenilen dersler" in enriched
    assert "ders-1" in enriched


def test_apply_to_prompt_unchanged_without_cards(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    assert apply_to_prompt(runtime, "TEMEL") == "TEMEL"
