from ahos.department_acceptance_bridge import DepartmentAcceptanceBridge


def _payload(kind):
    return {
        "kind": kind,
        "accepted": True,
        "evidence_hash": "abc",
        "human_review_required": False,
    }


def test_department_acceptance_bridge_passes_all_proofs():
    report = DepartmentAcceptanceBridge().evaluate({
        "studio_acceptance": _payload("studio"),
        "identity_acceptance": _payload("identity"),
        "language_acceptance": _payload("languages"),
    })
    assert report.passed is True
    assert report.proofs == {
        "studio_acceptance", "identity_acceptance", "language_acceptance"
    }


def test_department_acceptance_bridge_honors_human_review():
    payload = _payload("identity")
    payload["human_review_required"] = True
    payload["human_review_passed"] = False
    report = DepartmentAcceptanceBridge().evaluate({
        "studio_acceptance": _payload("studio"),
        "identity_acceptance": payload,
        "language_acceptance": _payload("languages"),
    })
    assert report.passed is False
    assert "identity_acceptance:human_review_pending" in report.blockers
