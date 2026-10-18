from ahos.deployment_probe import DeploymentProbe


def _receipt():
    return {
        "commit_sha": "abc123",
        "artifact_sha256": "a" * 64,
        "environment": "staging",
        "deployed_at": "2026-10-18T18:00:00+00:00",
        "healthcheck_passed": True,
        "rollback_ready": True,
        "secrets_externalized": True,
    }


def test_deployment_probe_passes_complete_receipt():
    assert DeploymentProbe().evaluate(_receipt()).passed is True


def test_deployment_probe_fails_without_rollback():
    receipt = _receipt()
    receipt["rollback_ready"] = False
    report = DeploymentProbe().evaluate(receipt)
    assert report.passed is False
    assert "rollback_not_ready" in report.blockers
