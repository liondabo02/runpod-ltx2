from datetime import datetime, timezone
import json

from ahos.verification_baseline import load_verification_baseline


def test_baseline_covers_only_proven_capabilities_before_verification_time(tmp_path):
    path = tmp_path / "verification-baseline.json"
    path.write_text(json.dumps({
        "schema": "ahos.verification-baseline.v1",
        "verified_at": "2026-10-18T16:30:00Z",
        "commit_sha": "abc",
        "platform": "windows",
        "proofs": {"coding_reliability": True, "department_runtime": False},
    }), encoding="utf-8")
    baseline, status = load_verification_baseline(path)
    assert status == "valid"
    assert baseline.covers("coding_reliability", "2026-10-10T00:00:00+00:00") is True
    assert baseline.covers("coding_reliability", "2026-10-19T00:00:00+00:00") is False
    assert baseline.covers("department_runtime", "2026-10-10T00:00:00+00:00") is False


def test_corrupted_baseline_fails_closed(tmp_path):
    path = tmp_path / "verification-baseline.json"
    path.write_text("{broken", encoding="utf-8")
    baseline, status = load_verification_baseline(path)
    assert baseline is None
    assert status == "invalid"


def test_missing_baseline_is_explicit(tmp_path):
    baseline, status = load_verification_baseline(tmp_path / "missing.json")
    assert baseline is None
    assert status == "missing"
