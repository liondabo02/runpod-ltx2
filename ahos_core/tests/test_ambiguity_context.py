from __future__ import annotations

from ahos.llm_executor import _ambiguity_context


def test_context_lists_every_occurrence_with_line_numbers() -> None:
    body = "alpha\nbeta\nreturn 1;\ngamma\n\ndelta\nreturn 1;\n"

    context = _ambiguity_context(body, "return 1;")

    assert "satır 3" in context
    assert "satır 7" in context
    assert "alpha" in context  # ±2 satır bağlam
    assert "delta" in context


def test_context_is_bounded() -> None:
    body = "\n".join(["x"] * 50 + ["return 1;"] * 20)

    context = _ambiguity_context(body, "return 1;", limit=3)

    assert context.count("--- eşleşme") == 3


def test_context_empty_when_no_match() -> None:
    assert _ambiguity_context("alpha\nbeta\n", "yok") == ""
