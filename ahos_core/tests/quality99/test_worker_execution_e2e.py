from ahos_quality99.worker_execution_e2e import run_worker_execution_e2e


def test_real_worker_engine_edits_tests_and_stops_at_owner_gate():
    report = run_worker_execution_e2e()
    assert report.passed is True
    assert report.changed_expected_file is True
    assert report.real_test_passed is True
    assert report.patch_evidence_present is True
    assert report.owner_gate_stopped_publish is True
    assert report.owner_repo_clean is True
