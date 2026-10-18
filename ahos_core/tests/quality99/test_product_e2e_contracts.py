from ahos_quality99.product_e2e_contracts import AndroidProofContract, BrowserProofContract


def test_android_contract_fails_without_real_evidence():
    report = AndroidProofContract().evaluate({})
    assert report.accepted is False
    assert report.blockers


def test_browser_contract_requires_clean_critical_flow():
    report = BrowserProofContract().evaluate({
        "commit_sha":"abc",
        "browser":"Chrome",
        "browser_version":"1",
        "base_url":"http://127.0.0.1",
        "navigation_passed":True,
        "critical_flow_passed":True,
        "console_errors":[],
        "captured_at":"2026-10-18T00:00:00+00:00",
    })
    assert report.accepted is True
