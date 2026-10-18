from ahos_quality99.memory_durability import run_memory_durability_rehearsal


def test_memory_survives_reopen_redacts_secrets_and_isolates_repositories():
    report = run_memory_durability_rehearsal()
    assert report.passed is True
    assert report.persisted_after_reopen is True
    assert report.secret_redacted is True
    assert report.repository_isolated is True
