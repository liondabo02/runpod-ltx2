"""Klon/web kabul araclari: ozellik ve duzen paritesi."""

from __future__ import annotations

import csv
from pathlib import Path

from ahos.clone_acceptance import REPLICA_DIR, accept, feature_parity, layout_parity


def _write_png(path: Path, blocks=()) -> None:
    from ahos.clone_acceptance import _load

    imgdiff = _load("ahos_replica_imgdiff_test", "imgdiff.py")
    width, height = 240, 320
    rows = [[(255, 255, 255) for _ in range(width)] for _ in range(height)]
    for x, y, w, h, colour in blocks:
        for yy in range(y, min(height, y + h)):
            for xx in range(x, min(width, x + w)):
                rows[yy][xx] = colour
    imgdiff.write_png(str(path), width, height, rows)


def _matrix(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["feature", "area", "priority", "original", "clone", "notes"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_vendored_template_is_not_shippable() -> None:
    result = feature_parity(REPLICA_DIR / "features.csv")
    assert result["feature_score"] == 0.0
    assert result["must_have_total"] > 0
    assert result["must_have_done"] == 0


def test_full_matrix_passes_acceptance(tmp_path) -> None:
    csv_path = _matrix(
        tmp_path / "features.csv",
        [
            {"feature": "sign up", "area": "onboarding", "priority": "must",
             "original": "yes", "clone": "yes", "notes": ""},
            {"feature": "book slot", "area": "booking", "priority": "must",
             "original": "yes", "clone": "yes", "notes": ""},
            {"feature": "dark mode", "area": "settings", "priority": "could",
             "original": "yes", "clone": "partial", "notes": ""},
        ],
    )

    passed, evidence = accept(csv_path, min_features=80.0)

    assert passed is True, evidence
    assert evidence["must_have_done"] == evidence["must_have_total"] == 2
    assert evidence["feature_score"] >= 80.0
    assert evidence["reasons"] == []


def test_missing_must_have_blocks_even_with_high_score(tmp_path) -> None:
    csv_path = _matrix(
        tmp_path / "features.csv",
        [
            {"feature": "sign up", "area": "onboarding", "priority": "must",
             "original": "yes", "clone": "no", "notes": ""},
            {"feature": "book slot", "area": "booking", "priority": "could",
             "original": "yes", "clone": "yes", "notes": ""},
        ],
    )

    passed, evidence = accept(csv_path, min_features=1.0)

    assert passed is False
    assert evidence["must_have_done"] == 0
    assert any("zorunlu" in reason for reason in evidence["reasons"])


def test_layout_identical_screens_score_full(tmp_path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _write_png(a, [(0, 0, 240, 40, (20, 20, 60))])
    _write_png(b, [(0, 0, 240, 40, (20, 20, 60))])

    report = layout_parity(a, b)

    assert report["score"] == 100.0


def test_layout_different_screen_fails_threshold(tmp_path) -> None:
    csv_path = _matrix(
        tmp_path / "features.csv",
        [
            {"feature": "sign up", "area": "onboarding", "priority": "must",
             "original": "yes", "clone": "yes", "notes": ""},
        ],
    )
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _write_png(a, [(0, 0, 240, 40, (20, 20, 60)), (20, 250, 120, 36, (40, 110, 230))])
    _write_png(b, [(0, 0, 240, 40, (20, 20, 60))])

    passed, evidence = accept(csv_path, original_png=a, clone_png=b, min_layout=95.0)

    assert passed is False
    assert evidence["layout_score"] < 95.0
    assert any("duzen" in reason for reason in evidence["reasons"])
