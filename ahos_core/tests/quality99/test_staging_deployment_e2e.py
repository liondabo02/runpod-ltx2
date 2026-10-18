from ahos_quality99.staging_deployment_e2e import run_staging_deployment_e2e


def test_isolated_staging_deploy_upgrade_and_rollback():
    report = run_staging_deployment_e2e()
    assert report.passed is True
    assert report.first_deploy_ok is True
    assert report.upgrade_ok is True
    assert report.rollback_ok is True
    assert report.production_mutation is False
