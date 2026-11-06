"""Project-local pytest acceptance: missing or failed checks cannot approve work."""
from __future__ import annotations

from ahos.acceptance import check_offline


def _gate(root):
    (root / "tools").mkdir()
    # The script is a trust marker, not executable acceptance logic.
    (root / "tools" / "check_offline.py").write_text(
        "raise RuntimeError('do not execute candidate gate')\n",
        encoding="utf-8",
    )


def test_project_local_pytest_passes(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _gate(root)
    (root / "tests").mkdir()
    (root / "app.py").write_text("VALUE = 42\n", encoding="utf-8")
    (root / "tests" / "test_ok.py").write_text(
        "from app import VALUE\ndef test_ok(): assert VALUE == 42\n",
        encoding="utf-8",
    )

    ok, detail = check_offline(root)

    assert ok is True, detail
    assert "1 passed / 0 failed" in detail


def test_project_local_pytest_failure_is_reported(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _gate(root)
    (root / "tests").mkdir()
    (root / "tests" / "test_fail.py").write_text(
        "def test_fail(): assert 1 == 2\n", encoding="utf-8"
    )

    ok, detail = check_offline(root)

    assert ok is False
    assert "failed" in detail
    assert "1 failed" in detail


def test_missing_suite_or_gate_is_fail_closed(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _gate(root)

    ok, detail = check_offline(root)

    assert ok is False
    assert "kabul testi yok" in detail

    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text(
        "def test_ok(): assert True\n", encoding="utf-8"
    )
    (root / "tools" / "check_offline.py").unlink()

    ok, detail = check_offline(root)

    assert ok is False
    assert "kabul testi yok" in detail
