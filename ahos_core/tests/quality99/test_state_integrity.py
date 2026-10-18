from ahos_quality99.state_integrity import run_state_integrity_rehearsal


def test_state_integrity_detects_json_hash_and_sqlite_corruption():
    report = run_state_integrity_rehearsal()
    assert report.passed is True
