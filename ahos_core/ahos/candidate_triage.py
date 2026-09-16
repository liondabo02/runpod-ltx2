from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .opportunity_intake import OpportunityCandidate, OpportunityCandidateStore


class CandidateDisposition(str, Enum):
    PRIORITY = "priority"
    REVIEW = "review"
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


_POSITIVE_TERMS: dict[str, int] = {
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
    "contract": 12,
    "contractor": 14,
    "freelance": 16,
}

_NEGATIVE_TERMS: dict[str, int] = {
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
}

_EMPLOYMENT_TERMS = (
    "full-time",
    "full time",
    "employee",
    "employment",
    "benefits",
    "salary",
    "years of experience",
    "bachelor",
    "degree",
    "shift",
)

_PROJECT_TERMS = (
    "contract",
    "contractor",
    "freelance",
    "project",
    "consulting",
    "consultant",
    "temporary",
    "part-time",
    "part time",
)


def _normalized_text(candidate: OpportunityCandidate) -> str:
    metadata_bits = []
    for key in ("company", "location", "tags", "position"):
        value = candidate.raw_metadata.get(key)
        if value:
            metadata_bits.append(str(value))
    text = " ".join(
        [
            candidate.title,
            candidate.description,
            candidate.category,
            *metadata_bits,
        ]
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def triage_candidate(candidate: OpportunityCandidate) -> CandidateTriage:
    text = _normalized_text(candidate)

    score = 30
    positive: list[str] = []
    negative: list[str] = []
    reasons: list[str] = []

    for term, weight in _POSITIVE_TERMS.items():
        if term in text:
            score += weight
            positive.append(term)

    for term, weight in _NEGATIVE_TERMS.items():
        if term in text:
            score -= weight
            negative.append(term)

    project_like = [term for term in _PROJECT_TERMS if term in text]
    employment_like = [term for term in _EMPLOYMENT_TERMS if term in text]

    if project_like:
        score += min(20, 6 * len(project_like))
        reasons.append("project/contract language detected")

    if employment_like and not project_like:
        score -= min(25, 5 * len(employment_like))
        reasons.append("looks like a human employment role")

    if candidate.category in {"software", "devops", "remote-work"}:
        score += 5
        reasons.append(f"source category: {candidate.category}")

    score = max(0, min(100, score))

    if employment_like and not project_like and score < 55:
        disposition = CandidateDisposition.HUMAN_JOB
    elif score >= 70:
        disposition = CandidateDisposition.PRIORITY
    elif score >= 50:
        disposition = CandidateDisposition.REVIEW
    else:
        disposition = CandidateDisposition.LOW_FIT

    if positive:
        reasons.append("matched useful technical/business terms")
    if negative:
        reasons.append("matched low-fit terms")

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
    )


def triage_candidates(
    candidates: Iterable[OpportunityCandidate],
) -> tuple[CandidateTriage, ...]:
    results = [triage_candidate(candidate) for candidate in candidates]
    results.sort(key=lambda item: (-item.score, item.title.lower(), item.candidate_id))
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
