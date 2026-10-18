import pytest

from ahos_quality99.bounded_process import BoundedProcessRunner
from ahos_quality99.browser_evidence import ControlCenterBrowserEvidence
from ahos_quality99.dashboard_consistency import DashboardConsistencyAuditor
from ahos_quality99.dashboard_flow_evidence import DashboardFlowEvidence
from ahos_quality99.model_routing import ModelEndpoint, ZeroCostSeparationRouter
from ahos_quality99.product_e2e_contracts import AndroidProofContract, BrowserProofContract
from ahos_quality99.quality_matrix import evaluate_quality
from ahos_quality99.worker_performance import WorkerOutcome


def test_bounded_process_rejects_invalid_limits(tmp_path):
    with pytest.raises(ValueError):
        BoundedProcessRunner(timeout_seconds=0)
    with pytest.raises(ValueError):
        BoundedProcessRunner(timeout_seconds=1, poll_seconds=0)
    with pytest.raises(ValueError):
        BoundedProcessRunner(timeout_seconds=1).run([], cwd=tmp_path)
    with pytest.raises(ValueError):
        BoundedProcessRunner(timeout_seconds=1).run(["echo"], cwd=tmp_path / "missing")


def test_browser_evidence_fail_closed_on_bad_payload():
    report = ControlCenterBrowserEvidence().evaluate({
        "browser": "Chrome",
        "browser_version": "x",
        "url": "http://127.0.0.1",
        "http_status": 500,
        "html_length": 10,
        "page_title": "wrong",
        "screenshot_sha256": "bad",
        "screenshot_size_bytes": 1,
        "browser_exit_code": 1,
        "isolated_runtime": False,
        "server_terminated": False,
        "captured_at": "x",
    })
    assert report.accepted is False
    assert len(report.blockers) >= 7


def test_dashboard_flow_fail_closed_on_worker_execution_and_bad_render():
    report = DashboardFlowEvidence().evaluate({
        "task_id": "A",
        "task_status": "running",
        "task_attempts": 1,
        "post_status": 500,
        "html_has_task_id": False,
        "html_has_task_title": False,
        "screenshot_sha256": "bad",
        "screenshot_size_bytes": 1,
        "isolated_runtime": False,
        "unique_port": False,
        "server_terminated": False,
    })
    assert report.accepted is False
    assert "worker_execution_detected" in report.blockers


def test_dashboard_consistency_rejects_invalid_and_extra_models():
    invalid = DashboardConsistencyAuditor().evaluate(
        queue_status={"counts": "bad", "tasks":[]},
        dashboard_coding={"counts": {}, "tasks":[]},
    )
    assert invalid.consistent is False
    mismatch = DashboardConsistencyAuditor().evaluate(
        queue_status={"counts": {}, "tasks":[{"task_id":"A"}]},
        dashboard_coding={"counts": {}, "tasks":[{"task_id":"B"}]},
    )
    assert "dashboard_missing:A" in mismatch.blockers
    assert "dashboard_extra:B" in mismatch.blockers


def test_model_router_rejects_paid_only_and_same_identity():
    paid = ZeroCostSeparationRouter().select((
        ModelEndpoint("paid", "both", 0.01),
    ))
    assert paid.allowed is False
    assert "zero_cost_builder_unavailable" in paid.blockers
    same = ZeroCostSeparationRouter().select((
        ModelEndpoint("only", "both", 0.0),
    ), preferred_builder="only", preferred_reviewer="only")
    assert same.allowed is False
    assert "builder_reviewer_not_separated" in same.blockers


def test_android_contract_accepts_complete_evidence_and_rejects_bad_hash():
    ok = AndroidProofContract().evaluate({
        "apk_sha256": "a" * 64,
        "device_model": "test",
        "android_version": "15",
        "install_passed": True,
        "launch_passed": True,
        "smoke_passed": True,
        "captured_at": "now",
    })
    assert ok.accepted is True
    bad = AndroidProofContract().evaluate({
        "apk_sha256": "bad",
        "device_model": "test",
        "android_version": "15",
        "install_passed": False,
        "launch_passed": False,
        "smoke_passed": False,
        "captured_at": "now",
    })
    assert bad.accepted is False


def test_browser_contract_rejects_console_and_navigation_failures():
    report = BrowserProofContract().evaluate({
        "commit_sha":"abc",
        "browser":"Chrome",
        "browser_version":"1",
        "base_url":"http://127.0.0.1",
        "navigation_passed":False,
        "critical_flow_passed":False,
        "console_errors":["boom"],
        "captured_at":"now",
    })
    assert report.accepted is False
    assert "browser_console_errors" in report.blockers


def test_quality_matrix_rejects_empty_input():
    with pytest.raises(ValueError):
        evaluate_quality(())


def test_worker_outcome_rejects_invalid_values():
    with pytest.raises(ValueError):
        WorkerOutcome("", True, True, 1)
    with pytest.raises(ValueError):
        WorkerOutcome("w", True, True, -1)
    with pytest.raises(ValueError):
        WorkerOutcome("w", True, True, 1, -1)
