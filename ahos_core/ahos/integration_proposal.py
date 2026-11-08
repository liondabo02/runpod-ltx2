from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .research_store import ResearchStore


class ProposalStatus(str, Enum): DRAFT = "draft"; WAITING_OWNER_APPROVAL = "waiting_owner_approval"
class IntegrationRisk(str, Enum): LOW = "low"; MEDIUM = "medium"; HIGH = "high"; CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class IntegrationProposal:
    proposal_id: str
    research_id: str
    evidence_ids: tuple[str, ...]
    title: str
    target_department: str
    proposed_by: str
    summary: str
    license_spdx: str
    source_commit: str
    risk: IntegrationRisk
    estimated_cost_usd: float
    external_side_effect: bool
    destructive: bool
    touches_secrets: bool
    tests: tuple[str, ...]
    rollback_plan: str
    status: ProposalStatus = ProposalStatus.WAITING_OWNER_APPROVAL


class IntegrationProposalBuilder:
    def __init__(self, store: ResearchStore) -> None: self.store = store

    def build(self, **values: object) -> IntegrationProposal:
        self.store.verify_integrity()
        evidence_ids = tuple(values.get("evidence_ids", ()))
        evidence = [self.store.get(str(i)) for i in evidence_ids]
        if not evidence_ids or any(e is None for e in evidence): raise ValueError("verified evidence required")
        research_id = str(values.get("research_id", ""))
        if any(e.research_id != research_id for e in evidence if e): raise ValueError("research mismatch")
        licenses = {e.license_spdx for e in evidence if e}; commits = {e.source_commit for e in evidence if e}
        if len(licenses) != 1 or len(commits) != 1 or next(iter(licenses)).upper() in {"UNKNOWN", "NONE", "NOASSERTION"}: raise ValueError("license/commit mismatch or blocked")
        tests = tuple(values.get("tests", ()))
        if not tests or not str(values.get("rollback_plan", "")).strip() or float(values.get("estimated_cost_usd", 0)) < 0: raise ValueError("tests, rollback and valid cost required")
        values["evidence_ids"], values["tests"] = evidence_ids, tests
        values["license_spdx"], values["source_commit"] = next(iter(licenses)), next(iter(commits))
        proposal = IntegrationProposal(**values)
        if proposal.status not in {ProposalStatus.DRAFT, ProposalStatus.WAITING_OWNER_APPROVAL}: raise ValueError("proposal cannot self-approve")
        return proposal
