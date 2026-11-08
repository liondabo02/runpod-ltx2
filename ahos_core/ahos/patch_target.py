"""Locate a patch target inside a file, and refuse to guess when ambiguous.

Two failure classes appear in real runs:

* the snippet is found in **several** places (``yama hedefi birden fazla``),
* the model copies the snippet with different indentation / whitespace.

``choose_target`` therefore matches whitespace-insensitively, reports every
candidate with its line number, and only applies an edit when the target is
unique — or when the caller supplies a line range that contains exactly one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    start: int
    end: int
    line: int
    context: str


class AmbiguousTarget(ValueError):
    def __init__(self, snippet_label: str, candidates: list[Candidate]) -> None:
        self.candidates = candidates
        lines = ", ".join(str(candidate.line) for candidate in candidates)
        super().__init__(
            f"'{snippet_label}' hedefi {len(candidates)} yerde bulundu "
            f"(satırlar: {lines}); dosya-satır aralığı veya daha uzun bağlam gerekli"
        )


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_candidates(text: str, snippet: str) -> list[Candidate]:
    """Whitespace-insensitive search returning every match with line numbers."""

    wanted = _squash(snippet)
    if not wanted:
        return []

    # Boşluk duyarsız eşleşme: parçalar arasında \s+ serbest.
    pattern = r"\s+".join(re.escape(part) for part in wanted.split(" "))
    matches: list[Candidate] = []
    for match in re.finditer(pattern, text):
        start, end = match.span()
        line = text.count("\n", 0, start) + 1
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        if line_end == -1:
            line_end = len(text)
        matches.append(
            Candidate(
                start=start,
                end=end,
                line=line,
                context=text[line_start:line_end][:160],
            )
        )
    return matches


def choose_target(
    text: str,
    snippet: str,
    *,
    line_range: tuple[int, int] | None = None,
    label: str = "snippet",
) -> Candidate:
    candidates = find_candidates(text, snippet)
    if line_range is not None:
        low, high = line_range
        inside = [c for c in candidates if low <= c.line <= high]
        if len(inside) == 1:
            return inside[0]
        if len(inside) > 1:
            raise AmbiguousTarget(label, inside)
        raise ValueError(
            f"'{label}' hedefi {low}-{high} satır aralığında bulunamadı"
        )

    if not candidates:
        raise ValueError(f"'{label}' hedefi dosyada bulunamadı")
    if len(candidates) > 1:
        raise AmbiguousTarget(label, candidates)
    return candidates[0]
