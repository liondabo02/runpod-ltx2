from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .autonomous_company import PersistentMissionQueue, QueueStatus, QueuedMission
from .candidate_triage import CandidateDisposition, CandidateTriage, triage_candidate
from .opportunity_intake import OpportunityCandidate, OpportunityCandidateStore


@dataclass(frozen=True, slots=True)
class OpportunityMissionDecision:
    candidate_id: str
    mission_id: str | None
    queued: bool
    primary_department: str | None
    reason: str


class QualifiedOpportunityMissionBridge:
    """Convert qualified local opportunity candidates into queued AHOS missions.

    The bridge is intentionally read-only with respect to the outside world.
    It never applies, bids, messages, publishes, purchases, pays, deploys, logs
    in, or touches credentials. It only writes mission metadata to the local
    persistent AHOS queue.
    """

    def __init__(self, queue: PersistentMissionQueue) -> None:
        self.queue = queue

    @staticmethod
    def _department_for(
        candidate: OpportunityCandidate,
        triage: CandidateTriage,
    ) -> str:
        text = " ".join(
            (
                candidate.title,
                candidate.description,
                candidate.category,
                " ".join(triage.matched_positive_terms),
            )
        ).lower()

        rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("marketing", ("marketing", "seo", "campaign")),
            ("sales", ("sales", "crm", "lead generation", "business development")),
            ("finance", ("finance", "accounting", "bookkeeping", "budget")),
            ("support", ("customer support", "customer service", "helpdesk", "support")),
            ("creative", ("design", "designer", "creative", "illustration", "animation")),
            ("data", ("data", "analytics", "machine learning", "analysis")),
            ("infrastructure", ("devops", "cloud", "infrastructure", "security", "ci/cd")),
            (
                "software",
                (
                    "automation",
                    "python",
                    "api",
                    "integration",
                    "software",
                    "developer",
                    "backend",
                    "react",
                    ".net",
                    "shopify",
                    "saas",
                    "workflow",
                ),
            ),
        )
        for department, terms in rules:
            if any(term in text for term in terms):
                return department

        return "research"

    @staticmethod
    def _objective(
        candidate: OpportunityCandidate,
        triage: CandidateTriage,
    ) -> str:
        return (
            "READ-ONLY OPPORTUNITY ASSESSMENT. "
            "Analyze the qualified business lead and prepare an internal recommendation. "
            "Do not contact anyone, apply, bid, message, publish, purchase, pay, deploy, "
            "log in, or use credentials. "
            f"Candidate title: {candidate.title}. "
            f"Source: {candidate.source_id}. "
            f"Category: {candidate.category}. "
            f"Opportunity URL: {candidate.item_url}. "
            f"Local triage score: {triage.score}/100. "
            f"Triage reasons: {', '.join(triage.reasons) or 'none'}."
        )

    def convert(
        self,
        candidate: OpportunityCandidate,
        *,
        triage: CandidateTriage | None = None,
    ) -> OpportunityMissionDecision:
        triage = triage or triage_candidate(candidate)

        if triage.disposition is not CandidateDisposition.BUSINESS_LEAD:
            return OpportunityMissionDecision(
                candidate_id=candidate.candidate_id,
                mission_id=None,
                queued=False,
                primary_department=None,
                reason=f"not a qualified business lead: {triage.disposition.value}",
            )

        mission_id = f"opportunity:{candidate.candidate_id}"
        existing = self.queue.get(mission_id)
        if existing is not None:
            return OpportunityMissionDecision(
                candidate_id=candidate.candidate_id,
                mission_id=mission_id,
                queued=False,
                primary_department=existing.primary_department,
                reason=f"already queued with status {existing.status.value}",
            )

        department = self._department_for(candidate, triage)
        mission = self.queue.enqueue(
            mission_id=mission_id,
            objective=self._objective(candidate, triage),
            primary_department=department,
            max_attempts=1,
        )

        return OpportunityMissionDecision(
            candidate_id=candidate.candidate_id,
            mission_id=mission.mission_id,
            queued=True,
            primary_department=mission.primary_department,
            reason="qualified business lead queued for read-only internal assessment",
        )

    def convert_many(
        self,
        candidates: Iterable[OpportunityCandidate],
    ) -> tuple[OpportunityMissionDecision, ...]:
        return tuple(self.convert(candidate) for candidate in candidates)

    def convert_store(
        self,
        candidate_store_path: str | Path,
    ) -> tuple[OpportunityMissionDecision, ...]:
        candidates = OpportunityCandidateStore(candidate_store_path).all()
        return self.convert_many(candidates)
