"""Uretim adimi dosya degistirmediyse 'tamam' denmez (no_change)."""

from __future__ import annotations

from types import SimpleNamespace

from ahos.project_qa import make_project_qa
from ahos.worker_runtime import WorkerExecutionResult


def _item(task_id: str) -> SimpleNamespace:
    return SimpleNamespace(task_id=task_id, required_capabilities=frozenset(),
                           department="software")


def _result(task_id: str, artifact) -> WorkerExecutionResult:
    return WorkerExecutionResult(
        task_id=task_id,
        worker_id="w-1",
        success=True,
        summary="tamam",
        artifacts=(str(artifact),),
    )


def _artifact(evidence, name):
    path = evidence / name
    path.write_text("kanit", encoding="utf-8")
    return path


def test_produce_without_any_file_change_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AHOS_REQUIRE_PRODUCTIVE_CHANGE", "1")
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    qa = make_project_qa(root, evidence)

    brief = qa(_item("M1:brief"), _result("M1:brief", _artifact(evidence, "b.json")), "qa-2")
    assert brief.passed is True, brief.summary

    produce = qa(_item("M1:produce"), _result("M1:produce", _artifact(evidence, "p.json")), "qa-2")
    assert produce.passed is False
    assert "no_change" in produce.summary


def test_produce_with_a_real_change_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("AHOS_REQUIRE_PRODUCTIVE_CHANGE", "1")
    root = tmp_path / "project"
    root.mkdir()
    source = root / "app.py"
    source.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    qa = make_project_qa(root, evidence)

    brief = qa(_item("M2:brief"), _result("M2:brief", _artifact(evidence, "b2.json")), "qa-2")
    assert brief.passed is True, brief.summary

    # Isci gercek bir degisiklik yapar.
    source.write_text(
        "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
        encoding="utf-8",
    )

    produce = qa(_item("M2:produce"), _result("M2:produce", _artifact(evidence, "p2.json")), "qa-2")
    assert produce.passed is True, produce.summary
