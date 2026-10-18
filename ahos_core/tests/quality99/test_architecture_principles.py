from ahos_quality99.architecture_principles import SystemDesignPrimerAudit


def test_architecture_audit_fails_closed_on_unproven_deployment_rollback():
    report = SystemDesignPrimerAudit().evaluate({
        "persistent_task_queue": True,
        "idempotency": True,
        "back_pressure": True,
        "bounded_concurrency": True,
        "health_checks": True,
        "failure_recovery": True,
        "data_integrity": True,
        "observability": True,
        "authority_boundary": True,
        "deployment_rollback": False,
    })
    assert report.passed is False
    assert report.gaps == ("deployment_rollback",)
