from __future__ import annotations

from ahos.candidate_triage import CandidateDisposition, triage_candidate
from ahos.opportunity_intake import OpportunityCandidate


def _candidate(
    title: str,
    description: str = "",
    raw_metadata: dict | None = None,
) -> OpportunityCandidate:
    return OpportunityCandidate(
        candidate_id=title.lower().replace(" ", "-"),
        source_id="test",
        source_url="https://example.test/feed",
        item_url="https://example.test/job",
        title=title,
        description=description,
        category="software",
        discovered_at="2026-09-16T12:00:00+00:00",
        raw_metadata=raw_metadata or {},
    )


def test_plural_contracts_title_is_not_project_signal() -> None:
    result = triage_candidate(
        _candidate(
            "Senior Contracts and Budget Associate",
            "Full-time employee role with salary and benefits.",
        )
    )
    assert result.explicit_project_signal is False
    assert result.disposition is not CandidateDisposition.BUSINESS_LEAD


def test_generic_consultant_title_is_not_project_signal() -> None:
    result = triage_candidate(
        _candidate(
            "Customer Support Consultant",
            "Full-time employee role with benefits.",
        )
    )
    assert result.explicit_project_signal is False
    assert result.disposition is not CandidateDisposition.BUSINESS_LEAD


def test_freelance_title_is_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Freelance Python Automation Developer",
            "Build API integrations and automate workflows.",
        )
    )
    assert result.explicit_project_signal is True
    assert result.disposition is CandidateDisposition.BUSINESS_LEAD


def test_exact_structured_contract_type_is_business_lead() -> None:
    result = triage_candidate(
        _candidate(
            "Python Developer",
            "Build an API integration.",
            {"employment_type": "contract"},
        )
    )
    assert result.explicit_project_signal is True
    assert result.disposition is CandidateDisposition.BUSINESS_LEAD


def test_description_contract_word_is_not_project_signal() -> None:
    result = triage_candidate(
        _candidate(
            "Senior Data Analyst",
            "Full-time employee role. Contract terms vary. Salary and benefits.",
        )
    )
    assert result.explicit_project_signal is False
    assert result.disposition is not CandidateDisposition.BUSINESS_LEAD
