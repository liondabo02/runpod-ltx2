from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .opportunity_intake import OpportunityCandidate, OpportunityCandidateStore


class CandidateDisposition(str, Enum):
    BUSINESS_LEAD = "business_lead"
    REVIEW = "review"
    TECH_JOB = "tech_job"
    LOW_FIT = "low_fit"
    HUMAN_JOB = "human_job"


@dataclass(frozen=True, slots=True)
class CandidateTriage:
    candidate_id: str
    title: str
    source_id: str
    item_url: str
    category: str
    score: int
    disposition: CandidateDisposition
    reasons: tuple[str, ...]
    matched_positive_terms: tuple[str, ...]
    matched_negative_terms: tuple[str, ...]
    explicit_project_signal: bool
    project_signal_source: str | None
    employment_signal: bool


_TECH_TERMS: dict[str, int] = {
    "automation": 18,
    "python": 16,
    "api": 14,
    "integration": 14,
    "software engineer": 12,
    "backend": 12,
    "developer": 10,
    "devops": 10,
    "data": 8,
    "ai": 8,
    "machine learning": 8,
    "workflow": 8,
    "cloud": 6,
    "saas": 6,
    "security": 5,
    "analytics": 5,
    "shopify": 6,
    "react": 5,
    ".net": 5,
}

_LOW_FIT_TERMS: dict[str, int] = {
    "nurse": 35,
    "physician": 40,
    "driver": 30,
    "warehouse": 28,
    "labourer": 32,
    "laborer": 32,
    "receptionist": 22,
    "voice over": 18,
    "customer service": 15,
    "sales development representative": 16,
    "account manager": 12,
    "aircraft": 18,
    "care navigator": 20,
    "healthcare assistant": 20,
    "mechanic": 18,
}

# These are strong enough ONLY when they occur in the title or structured
# job-type metadata. We intentionally do not trust arbitrary description text
# because job-board boilerplate can contain words like "contract".
_STRONG_PROJECT_TITLE_TERMS = (
    "freelance",
    "freelancer",
    "contractor",
    "independent contractor",
    "consultant",
    "consulting",
    "contract ",
    " contract",
    "fixed-term",
    "fixed term",
    "project-based",
    "project based",
    "temporary",
)

_STRUCTURED_PROJECT_VALUES = (
    "freelance",
    "contract",
    "contractor",
    "consulting",
    "consultant",
    "temporary",
    "fixed-term",
    "fixed term",
    "project",
)

_EMPLOYMENT_SIGNALS = (
    "full-time",
    "full time",
    "permanent",
    "employee",
    "employment",
    "benefits",
    "salary",
    "annual salary",
    "years of experience",
    "bachelor",
    "degree",
    "401k",
    "401(k)",
    "pto",
    "paid time off",
    "health insurance",
    "vacation",
    "shift",
    "equity",
)

_DELIVERABLE_SIGNALS = (
    "build ",
    "implement ",
    "integrate ",
    "migrate ",
    "automate ",
    "develop ",
    "design ",
    "deploy ",
    "fix ",
    "setup ",
    "set up ",
    "audit ",
    "optimize ",
)


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _full_text(candidate: OpportunityCandidate) -> str:
    metadata_bits = []
    for key in ("company", "location", "tags", "position"):
        value = candidate.raw_metadata.get(key)
        if value:
            metadata_bits.append(str(value))
    return _normalize(
        " ".join(
            [
                candidate.title,
                candidate.description,
                candidate.category,
                *metadata_bits,
            ]
        )
    )


def _project_signal(candidate: OpportunityCandidate) -> tuple[bool, str | None]:
    title = _normalize(candidate.title)
    if any(term in title for term in _STRONG_PROJECT_TITLE_TERMS):
        return True, "title"

    for key in ("type", "job_type", "employment_type", "contract_type"):
        value = _normalize(candidate.raw_metadata.get(key))
        if value and any(term in value for term in _STRUCTURED_PROJECT_VALUES):
            return True, f"metadata:{key}"

    return False, None


def triage_candidate(candidate: OpportunityCandidate) -> CandidateTriage:
    text = _full_text(candidate)
    score = 25
    positive: list[str] = []
    negative: list[str] = []
    reasons: list[str] = []

    for term, weight in _TECH_TERMS.items():
        if term in text:
            score += weight
            positive.append(term)

    for term, weight in _LOW_FIT_TERMS.items():
        if term in text:
            score -= weight
            negative.append(term)

    explicit_project_signal, signal_source = _project_signal(candidate)
    employment_terms = [term for term in _EMPLOYMENT_SIGNALS if term in text]
    deliverables = [term for term in _DELIVERABLE_SIGNALS if term in text]
    employment_signal = bool(employment_terms)

    if explicit_project_signal:
        score += 30
        reasons.append(f"strong project signal from {signal_source}")

    if deliverables:
        score += min(12, 3 * len(deliverables))
        reasons.append("delivery-oriented language")

    if employment_signal and not explicit_project_signal:
        score -= min(35, 6 * len(employment_terms))
        reasons.append("employment-style listing")

    if candidate.category in {"software", "devops", "remote-work"}:
        score += 5

    score = max(0, min(100, score))

    # A BUSINESS_LEAD requires a strong signal from title/structured metadata.
    # Technical relevance alone can never promote a normal employee listing.
    if explicit_project_signal and score >= 65:
        disposition = CandidateDisposition.BUSINESS_LEAD
    elif explicit_project_signal:
        disposition = CandidateDisposition.REVIEW
    elif employment_signal and positive:
        disposition = CandidateDisposition.TECH_JOB
    elif employment_signal:
        disposition = CandidateDisposition.HUMAN_JOB
    elif score >= 55 and positive:
        disposition = CandidateDisposition.REVIEW
    else:
        disposition = CandidateDisposition.LOW_FIT

    if positive:
        reasons.append("technical relevance detected")
    if negative:
        reasons.append("low-fit role signals detected")

    return CandidateTriage(
        candidate_id=candidate.candidate_id,
        title=candidate.title,
        source_id=candidate.source_id,
        item_url=candidate.item_url,
        category=candidate.category,
        score=score,
        disposition=disposition,
        reasons=tuple(reasons),
        matched_positive_terms=tuple(sorted(set(positive))),
        matched_negative_terms=tuple(sorted(set(negative))),
        explicit_project_signal=explicit_project_signal,
        project_signal_source=signal_source,
        employment_signal=employment_signal,
    )


def triage_candidates(
    candidates: Iterable[OpportunityCandidate],
) -> tuple[CandidateTriage, ...]:
    results = [triage_candidate(candidate) for candidate in candidates]
    rank = {
        CandidateDisposition.BUSINESS_LEAD: 0,
        CandidateDisposition.REVIEW: 1,
        CandidateDisposition.TECH_JOB: 2,
        CandidateDisposition.LOW_FIT: 3,
        CandidateDisposition.HUMAN_JOB: 4,
    }
    results.sort(
        key=lambda item: (
            rank[item.disposition],
            -item.score,
            item.title.lower(),
            item.candidate_id,
        )
    )
    return tuple(results)


def triage_store(
    candidate_store_path: str | Path,
    output_path: str | Path,
) -> tuple[CandidateTriage, ...]:
    candidates = OpportunityCandidateStore(candidate_store_path).all()
    results = triage_candidates(candidates)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for result in results:
            record = asdict(result)
            record["disposition"] = result.disposition.value
            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
    return results
