from __future__ import annotations

import pytest

from ahos.patch_target import AmbiguousTarget, choose_target, find_candidates

SAMPLE = """function a() {
  return 1;
}

function b() {
  return 1;
}
"""


def test_unique_target_is_returned() -> None:
    text = "alpha\nbeta\ngamma\n"
    target = choose_target(text, "beta")

    assert target.line == 2
    assert text[target.start:target.end] == "beta"


def test_duplicate_snippet_raises_with_line_numbers() -> None:
    with pytest.raises(AmbiguousTarget) as error:
        choose_target(SAMPLE, "return 1;")

    lines = [candidate.line for candidate in error.value.candidates]
    assert lines == [2, 6]
    assert "2 yerde" in str(error.value)


def test_line_range_disambiguates() -> None:
    target = choose_target(SAMPLE, "return 1;", line_range=(5, 7))

    assert target.line == 6
    assert SAMPLE[target.start:target.end] == "return 1;"


def test_line_range_without_match_is_reported() -> None:
    with pytest.raises(ValueError, match="bulunamadı"):
        choose_target(SAMPLE, "return 1;", line_range=(20, 30))


def test_whitespace_differences_are_tolerated() -> None:
    text = "if (x) {\n    doThing();\n}\n"
    target = choose_target(text, "if (x) { doThing(); }".replace(" ", "\n "))

    assert target.line == 1


def test_find_candidates_returns_every_hit() -> None:
    assert len(find_candidates("a a a", "a")) == 3
