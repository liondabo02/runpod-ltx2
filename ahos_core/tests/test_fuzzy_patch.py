"""Whitespace-tolerant patch application and queue recovery."""

from __future__ import annotations

from pathlib import Path

from ahos.llm_executor import ModelEdit, ModelError, _fuzzy_replace, _flexible_pattern


def test_flexible_pattern_matches_whitespace_variants() -> None:
    import re

    pattern = _flexible_pattern("const a = 1;\n  const b = 2;")
    assert re.search(pattern, "const  a = 1;\n    const b = 2;")


def test_fuzzy_replace_applies_single_match() -> None:
    text = "line one\n    line two\nline three"
    result = _fuzzy_replace(text, "line one\n  line two", "REPLACED")
    assert result is not None
    assert result.startswith("REPLACED")


def test_fuzzy_replace_refuses_ambiguous_match() -> None:
    text = "x = 1\nx = 1\n"
    assert _fuzzy_replace(text, "x  =  1", "y") is None


def test_patch_applies_when_only_indentation_differs(tmp_path) -> None:
    target = tmp_path / "a.js"
    target.write_text("function f() {\n    return 1;\n}\n", encoding="utf-8")
    edit = ModelEdit(path="a.js", find="function f() {\n  return 1;\n}", replace="function f() {\n  return 2;\n}")

    edit.apply(tmp_path)

    assert "return 2" in target.read_text(encoding="utf-8")


def test_patch_still_fails_when_target_absent(tmp_path) -> None:
    target = tmp_path / "a.js"
    target.write_text("const x = 1;\n", encoding="utf-8")
    edit = ModelEdit(path="a.js", find="const y = 2;", replace="const y = 3;")

    try:
        edit.apply(tmp_path)
    except ModelError as exc:
        assert "bulundu" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("olmayan hedef uygulanmamalı")
