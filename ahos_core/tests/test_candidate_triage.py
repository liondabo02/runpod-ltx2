from __future__ import annotations

from ahos.candidate_triage import CandidateDisposition, triage_candidate
from ahos.opportunity_intake import OpportunityCandidate


def _candidate(
    title: str,
    description: str,
    category: str = "software",
    raw_metadata: dict | None = None,
) -> OpportunityCandidate:
    return OpportunityCandidate(
        candidate_id=title.lower().replace(" ", "-"),
        source_id="test",
        source_url="https://example.test/feed",
        item_url="https://example.test/job",
        title=title,
        description=description,
        category=category,
        discovered_at="2026-09-16T12:00:00+00:00",
        raw_metadata=raw_metadata or {},
    )


def test_contract_word_in_boilerplate_does_not_create_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Senior Data Analyst",
            "Full-time employee role. Contract terms may vary by jurisdiction. Salary and benefits included.",
        )
    )
    assert result.explicit_project_signal is False
    assert result.disposition is CandidateDisposition.TECH_JOB


def test_title_freelance_is_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Freelance Python Automation Developer",
            "Build API integrations and automate workflows.",
        )
    )
    assert result.explicit_project_signal is True
    assert result.project_signal_source == "title"
    assert result.disposition is CandidateDisposition.BUSINESS_LEAD


def test_structured_contract_type_is_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Python Developer",
            "Build an API integration.",
            raw_metadata={"employment_type": "contract"},
        )
    )
    assert result.explicit_project_signal is True
    assert result.project_signal_source == "metadata:employment_type"
    assert result.disposition is CandidateDisposition.BUSINESS_LEAD


def test_full_time_technical_job_never_becomes_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Senior Software Engineer",
            "Full-time employee role with salary, benefits, degree and 5 years of experience. Build backend APIs.",
        )
    )
    assert result.disposition is CandidateDisposition.TECH_JOB
