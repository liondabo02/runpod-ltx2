from __future__ import annotations

from ahos.candidate_triage import CandidateDisposition, triage_candidate
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


def test_contract_automation_is_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Python Automation Contractor",
            "Independent contractor needed to build API integrations and automate workflows.",
        )
    )
    assert result.explicit_project_signal is True
    assert result.disposition is CandidateDisposition.BUSINESS_LEAD


def test_full_time_technical_job_is_not_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Senior Software Engineer",
            "Full-time employee role with salary, benefits and 5 years of experience required. Build backend APIs.",
        )
    )
    assert result.employment_signal is True
    assert result.disposition is CandidateDisposition.TECH_JOB


def test_nontechnical_human_job_is_not_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Registered Nurse",
            "Full-time employee role with benefits and shifts.",
            category="remote-work",
        )
    )
    assert result.disposition in {
        CandidateDisposition.HUMAN_JOB,
        CandidateDisposition.LOW_FIT,
    }


def test_consulting_project_can_be_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "API Integration Consultant",
            "Consulting engagement to integrate a CRM API and deploy automation.",
        )
    )
    assert result.disposition is CandidateDisposition.BUSINESS_LEAD
