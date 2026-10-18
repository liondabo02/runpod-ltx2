from ahos.department_overview import department_overview
from ahos.department_structure import CORE_DEPARTMENTS
from ahos.control_center import ControlCenterState, render_dashboard


def test_overview_separates_evidence_approval_and_provider_wait():
    tasks = [
        {"department": "research", "status": "waiting_provider", "next_retry_at": "2026-10-04T21:00:00+00:00"},
        {"department": "research", "status": "owner_approved", "artifact_hash": "abc"},
        {"department": "research", "status": "retries_exhausted"},
        {"department": "research", "status": "superseded", "artifact_hash": "old"},
        {"department": "software", "status": "blocked"},
    ]
    rows = department_overview(tasks)
    assert [r["department"] for r in rows] == list(CORE_DEPARTMENTS)
    research = next(r for r in rows if r["department"] == "research")
    assert research["artifact_count"] == research["owner_approved"] == research["waiting_provider"] == research["failed"] == 1
    assert research["production_readiness"] == "not_audited"
    assert research["next_retry_at"] == tasks[0]["next_retry_at"]
    assert next(r for r in rows if r["department"] == "software")["blocked"] == 1
    assert tasks[3]["status"] == "superseded"


def test_dashboard_and_api_expose_all_departments_without_inventing_completion(tmp_path):
    state = ControlCenterState(tmp_path / "runtime")
    snap = state.snapshot()
    assert len(snap["departments"]["overview"]) == len(CORE_DEPARTMENTS)
    assert all(row["production_readiness"] == "not_audited" for row in snap["departments"]["overview"])
    html = render_dashboard(snap)
    assert "Department evidence overview" in html
    assert "Approved drafts" in html
    assert "not_audited" in html
