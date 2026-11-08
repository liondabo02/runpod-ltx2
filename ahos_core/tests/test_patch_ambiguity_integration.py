from __future__ import annotations

from pathlib import Path

import pytest

from ahos.llm_executor import ModelEdit, ModelError
from ahos.patch_target import AmbiguousTarget, choose_target


def _file(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_unique_patch_applies(tmp_path) -> None:
    target = _file(tmp_path, "a.js", "line1\nline2\nline3\n")

    ModelEdit(path="a.js", find="line2", replace="LINE2").apply(tmp_path)

    assert "LINE2" in target.read_text(encoding="utf-8")


def test_whitespace_tolerant_patch_still_applies(tmp_path) -> None:
    target = _file(tmp_path, "b.js", "function a() {\n    return 1;\n}\n")

    ModelEdit(path="b.js", find="function a() { return 1; }", replace="// yeni").apply(tmp_path)

    assert target.read_text(encoding="utf-8").strip().startswith("// yeni")


def test_ambiguous_patch_reports_line_numbers(tmp_path) -> None:
    _file(tmp_path, "c.js", "return 1;\n\nreturn 1;\n")

    with pytest.raises(ModelError) as error:
        ModelEdit(path="c.js", find="return 1;", replace="return 2;").apply(tmp_path)

    message = str(error.value)
    assert "satır" in message.lower() or "line" in message.lower()
    assert "2" in message


def test_choose_target_line_range_resolves_ambiguity(tmp_path) -> None:
    text = "a\nreturn 1;\n\nreturn 1;\n"
    chosen = choose_target(text, "return 1;", line_range=(4, 5))

    assert chosen.line == 4


def test_ambiguous_target_exposes_candidates(tmp_path) -> None:
    text = "x\nreturn 1;\nreturn 1;\n"

    with pytest.raises(AmbiguousTarget) as error:
        choose_target(text, "return 1;")

    assert [candidate.line for candidate in error.value.candidates] == [2, 3]
