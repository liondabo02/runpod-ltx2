from __future__ import annotations

from ahos.gate_delta import failure_lines, gate_acceptable, new_failures


def test_failure_lines_detects_turkish_and_english() -> None:
    output = "sözdizimi geçti\nönbellek dışı: veli.html\n3 sorun bulundu.\nOK"

    lines = failure_lines(output)

    assert any("önbellek dışı" in line for line in lines)
    assert any("sorun bulundu" in line for line in lines)
    assert not any(line == "ok" for line in lines)


def test_numbers_are_normalized() -> None:
    assert failure_lines("3 sorun bulundu") == failure_lines("9 sorun bulundu")


def test_no_new_failures_when_identical() -> None:
    before = "önbellek dışı: a.js\n2 sorun bulundu"
    after = "önbellek dışı: a.js\n2 sorun bulundu"

    assert new_failures(before, after) == set()


def test_new_failure_detected() -> None:
    before = "önbellek dışı: a.js"
    after = "önbellek dışı: a.js\nsözdizimi hatası: b.js"

    added = new_failures(before, after)

    assert any("sözdizimi" in item for item in added)


def test_gate_accepts_when_after_passes() -> None:
    ok, note = gate_acceptable(False, "3 sorun bulundu", True, "temiz")

    assert ok is True
    assert note == ""


def test_gate_accepts_pre_existing_failure_without_new_errors() -> None:
    baseline = "önbellek dışı: a.js\n1 sorun bulundu"
    after = "önbellek dışı: a.js\n1 sorun bulundu"

    ok, note = gate_acceptable(False, baseline, False, after)

    assert ok is True
    assert "delta" in note


def test_gate_rejects_new_failure() -> None:
    baseline = "1 sorun bulundu"
    after = "1 sorun bulundu\nsözdizimi hatası: x.js"

    ok, note = gate_acceptable(False, baseline, False, after)

    assert ok is False
    assert "yeni kapı hatası" in note


def test_gate_rejects_failure_when_baseline_was_clean() -> None:
    ok, note = gate_acceptable(True, "temiz", False, "sözdizimi hatası")

    assert ok is False
    assert note == "kapı düştü"


def test_acceptable_when_both_clean() -> None:
    ok, _ = gate_acceptable(True, "temiz", True, "temiz")
    assert ok is True
