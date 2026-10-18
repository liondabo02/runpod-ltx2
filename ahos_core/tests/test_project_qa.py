from __future__ import annotations

from pathlib import Path

from ahos.project_qa import make_project_qa
from ahos.worker_runtime import WorkerExecutionResult
from ahos.workforce_execution import WorkItem


def _web_project(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "www").mkdir(parents=True)
    (root / "www" / "index.html").write_text(
        '<html><head></head><body><div id="stage"></div></body></html>',
        encoding="utf-8",
    )
    return root


def _non_web_project(tmp_path: Path) -> Path:
    root = tmp_path / "py"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text("print(1)\n", encoding="utf-8")
    return root


def _evidence(tmp_path: Path) -> Path:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "out.md").write_text("ok", encoding="utf-8")
    return evidence


def _item(step: str) -> WorkItem:
    return WorkItem(
        task_id=f"m1:{step}",
        title="görev",
        department="oyun",
        required_capabilities=frozenset({"qa"}),
    )


def _result(step: str, evidence: Path) -> WorkerExecutionResult:
    return WorkerExecutionResult(
        task_id=f"m1:{step}",
        worker_id="worker-1",
        success=True,
        summary="üretim tamam",
        artifacts=(str(evidence / "out.md"),),
    )


def test_web_project_passes_asset_gate(tmp_path) -> None:
    root = _web_project(tmp_path)
    evidence = _evidence(tmp_path)
    qa = make_project_qa(root, evidence)

    decision = qa(_item("produce"), _result("produce", evidence), "qa-01")

    assert decision.passed is True


def test_non_web_project_is_not_blocked_by_web_gate(tmp_path) -> None:
    root = _non_web_project(tmp_path)
    evidence = _evidence(tmp_path)
    qa = make_project_qa(root, evidence)

    decision = qa(_item("produce"), _result("produce", evidence), "qa-01")

    assert decision.passed is True, decision.summary


def test_missing_artifact_fails_with_reason(tmp_path) -> None:
    root = _web_project(tmp_path)
    evidence = _evidence(tmp_path)
    qa = make_project_qa(root, evidence)
    result = WorkerExecutionResult(
        task_id="m1:produce",
        worker_id="worker-1",
        success=True,
        summary="kanıtsız",
        artifacts=(),
    )

    decision = qa(_item("produce"), result, "qa-01")

    assert decision.passed is False
    assert "kanıt" in decision.summary


def test_producer_cannot_verify_own_work(tmp_path) -> None:
    root = _web_project(tmp_path)
    evidence = _evidence(tmp_path)
    qa = make_project_qa(root, evidence)
    result = _result("produce", evidence)

    decision = qa(_item("produce"), result, "worker-1")

    assert decision.passed is False
    assert "kendi" in decision.summary
