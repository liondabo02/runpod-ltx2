from __future__ import annotations

from pathlib import Path

from ahos.acceptance_suite import run_acceptance


def _gate(project: Path, ok: bool = True) -> None:
    tools = project / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "check_offline.py").write_text(
        "print('temiz')\nraise SystemExit(0)\n"
        if ok
        else "print('bozuk')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )


def test_valid_js_change_passes(tmp_path) -> None:
    _gate(tmp_path, ok=True)
    (tmp_path / "a.js").write_text("const x = 1;\n", encoding="utf-8")

    result = run_acceptance(tmp_path, ["a.js"])

    assert result.ok is True
    assert any("node --check" in name for name, _, _ in result.checks)


def test_broken_js_fails_even_if_gate_passes(tmp_path) -> None:
    _gate(tmp_path, ok=True)
    (tmp_path / "a.js").write_text("const x = ;\n", encoding="utf-8")

    result = run_acceptance(tmp_path, ["a.js"])

    assert result.ok is False
    assert "node --check" in result.summary


def test_missing_gate_blocks(tmp_path) -> None:
    (tmp_path / "a.js").write_text("const x = 1;\n", encoding="utf-8")

    result = run_acceptance(tmp_path, ["a.js"])

    assert result.ok is False
    assert "yok" in result.summary


def test_python_syntax_is_checked(tmp_path) -> None:
    _gate(tmp_path, ok=True)
    (tmp_path / "mod.py").write_text("def f(:\n    pass\n", encoding="utf-8")

    result = run_acceptance(tmp_path, ["mod.py"])

    assert result.ok is False
    assert "py_compile" in result.summary


def test_missing_changed_file_is_failure(tmp_path) -> None:
    _gate(tmp_path, ok=True)

    result = run_acceptance(tmp_path, ["yok.js"])

    assert result.ok is False
    assert "bulunamadı" in result.summary


def test_summary_reports_check_count(tmp_path) -> None:
    _gate(tmp_path, ok=True)
    (tmp_path / "a.js").write_text("const x = 1;\n", encoding="utf-8")

    result = run_acceptance(tmp_path, ["a.js"])

    assert str(len(result.checks)) in result.summary
