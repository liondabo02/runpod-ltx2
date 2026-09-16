from __future__ import annotations

from ahos.candidate_triage import CandidateDisposition, triage_candidate, triage_candidates
from ahos.opportunity_intake import OpportunityCandidate


def _candidate(title: str, description: str, category: str = "software") -> OpportunityCandidate:
    return OpportunityCandidate(
        candidate_id=title.lower().replace(" ", "-"),
        source_id="test",
        source_url="https://example.test/feed",
        item_url="https://example.test/job",
        title=title,
        description=description,
        category=category,
        discovered_at="2026-09-16T12:00:00+00:00",
        raw_metadata={},
    )


def test_project_automation_work_scores_high() -> None:
    result = triage_candidate(
        _candidate(
            "Python Automation Contractor",
            "Freelance project to build API integrations and workflow automation.",
        )
    )

    assert result.score >= 70
    assert result.disposition is CandidateDisposition.PRIORITY


def test_human_non_software_role_scores_low() -> None:
    result = triage_candidate(
        _candidate(
            "Registered Nurse",
            "Full-time employee role with benefits and shifts.",
            category="remote-work",
        )
    )

    assert result.score < 50
    assert result.disposition in {
        CandidateDisposition.HUMAN_JOB,
        CandidateDisposition.LOW_FIT,
    }


def test_ranking_is_deterministic() -> None:
    results = triage_candidates(
        (
            _candidate("General Assistant", "Full-time employee role."),
            _candidate("API Integration Contractor", "Contract Python automation project."),
        )
    )

    assert results[0].title == "API Integration Contractor"
