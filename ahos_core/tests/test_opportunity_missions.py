from pathlib import Path

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.candidate_triage import CandidateDisposition, CandidateTriage
from ahos.opportunity_intake import OpportunityCandidate
from ahos.opportunity_missions import QualifiedOpportunityMissionBridge


def candidate(
    *,
    candidate_id: str = "cand-1",
    title: str = "Freelance Python Automation Developer",
    description: str = "Build and integrate a Python API automation workflow.",
    category: str = "software",
):
    return OpportunityCandidate(
        candidate_id=candidate_id,
        source_id="test-source",
        source_url="https://example.test/feed",
        item_url=f"https://example.test/{candidate_id}",
        title=title,
        description=description,
        category=category,
        discovered_at="2026-09-19T00:00:00+00:00",
        raw_metadata={},
    )


def triage_for(c, disposition=CandidateDisposition.BUSINESS_LEAD, score=90):
    return CandidateTriage(
        candidate_id=c.candidate_id,
        title=c.title,
        source_id=c.source_id,
        item_url=c.item_url,
        category=c.category,
        score=score,
        disposition=disposition,
        reasons=("strong project signal", "technical relevance detected"),
        matched_positive_terms=("automation", "python", "api"),
        matched_negative_terms=(),
        explicit_project_signal=True,
        project_signal_source="title:freelance",
        employment_signal=False,
    )


def test_qualified_business_lead_becomes_persistent_pending_mission(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    bridge = QualifiedOpportunityMissionBridge(queue)
    c = candidate()

    decision = bridge.convert(c, triage=triage_for(c))

    assert decision.queued is True
    assert decision.primary_department == "software"

    mission = queue.get("opportunity:cand-1")
    assert mission is not None
    assert mission.status is QueueStatus.PENDING
    assert mission.primary_department == "software"
    assert "READ-ONLY OPPORTUNITY ASSESSMENT" in mission.objective


def test_non_business_lead_is_not_queued(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    bridge = QualifiedOpportunityMissionBridge(queue)
    c = candidate()

    decision = bridge.convert(
        c,
        triage=triage_for(c, disposition=CandidateDisposition.TECH_JOB, score=80),
    )

    assert decision.queued is False
    assert queue.list() == ()


def test_duplicate_conversion_is_idempotent(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    bridge = QualifiedOpportunityMissionBridge(queue)
    c = candidate()
    t = triage_for(c)

    first = bridge.convert(c, triage=t)
    second = bridge.convert(c, triage=t)

    assert first.queued is True
    assert second.queued is False
    assert "already queued" in second.reason
    assert len(queue.list()) == 1


def test_department_selection_handles_creative_lead(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    bridge = QualifiedOpportunityMissionBridge(queue)
    c = candidate(
        candidate_id="creative-1",
        title="Freelance Animation Designer",
        description="Design animation assets for a project.",
        category="creative",
    )
    t = CandidateTriage(
        candidate_id=c.candidate_id,
        title=c.title,
        source_id=c.source_id,
        item_url=c.item_url,
        category=c.category,
        score=85,
        disposition=CandidateDisposition.BUSINESS_LEAD,
        reasons=("strong project signal",),
        matched_positive_terms=(),
        matched_negative_terms=(),
        explicit_project_signal=True,
        project_signal_source="title:freelance",
        employment_signal=False,
    )

    decision = bridge.convert(c, triage=t)
    assert decision.primary_department == "creative"


def test_objective_explicitly_forbids_external_actions(tmp_path: Path):
    queue = PersistentMissionQueue(tmp_path / "missions.db")
    bridge = QualifiedOpportunityMissionBridge(queue)
    c = candidate()
    bridge.convert(c, triage=triage_for(c))

    mission = queue.get("opportunity:cand-1")
    text = mission.objective.lower()
    for forbidden in (
        "do not contact",
        "apply",
        "bid",
        "message",
        "publish",
        "purchase",
        "pay",
        "deploy",
        "credentials",
    ):
        assert forbidden in text
