from control_plane.core import Policy


def test_paid_actions_require_approval():
    reasons = Policy().approval_reasons("Run a paid RunPod GPU job")
    assert "paid/external-spend action" in reasons


def test_destructive_actions_require_approval():
    reasons = Policy().approval_reasons("delete the production volume")
    assert "destructive action" in reasons


def test_safe_research_needs_no_approval():
    assert Policy().approval_reasons("review GitHub docs and CI logs") == []
