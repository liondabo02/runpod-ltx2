from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from .studio_executor import STAGES


@dataclass(frozen=True, slots=True)
class StudioReleaseReadiness:
    ready: bool
    blockers: tuple[str, ...]
    execution_ledger_hash: str
    owner_release_hash: str


def _hash_mapping(value: Mapping[str, object]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class StudioReleaseOrchestrator:
    """Read-only final studio gate.

    It binds execution, delivery QA, and explicit owner release intent. It never
    publishes, deploys, spends money, or mutates the execution ledger.
    """

    def evaluate(
        self,
        *,
        execution_ledger: Mapping[str, object],
        delivery_evidence: Mapping[str, object],
        owner_release: Mapping[str, object],
    ) -> StudioReleaseReadiness:
        blockers: list[str] = []

        stages = execution_ledger.get("stages")
        if not isinstance(stages, Mapping):
            blockers.append("execution:missing_stages")
        else:
            for stage in STAGES:
                row = stages.get(stage)
                if not isinstance(row, Mapping) or row.get("status") != "completed":
                    blockers.append(f"execution:{stage}_not_completed")
        if execution_ledger.get("status") != "awaiting_final_owner_release":
            blockers.append("execution:not_waiting_final_owner_release")
        if execution_ledger.get("publishing_enabled") is not False:
            blockers.append("execution:publishing_must_remain_disabled")

        if delivery_evidence.get("release_candidate_ready") is not True:
            blockers.append("delivery:not_ready")
        delivery_hash = str(delivery_evidence.get("evidence_hash") or "")
        if len(delivery_hash) != 64:
            blockers.append("delivery:invalid_evidence_hash")

        if owner_release.get("owner_approved") is not True:
            blockers.append("owner:final_release_not_approved")
        if owner_release.get("publish_requested") is True:
            blockers.append("owner:publish_must_be_separate_action")
        if owner_release.get("episode_id") != execution_ledger.get("episode_id"):
            blockers.append("owner:episode_mismatch")
        decision_hash = str(owner_release.get("decision_hash") or "")
        unsigned = dict(owner_release)
        unsigned.pop("decision_hash", None)
        expected = _hash_mapping(unsigned)
        if decision_hash != expected:
            blockers.append("owner:decision_integrity_failed")

        return StudioReleaseReadiness(
            ready=not blockers,
            blockers=tuple(sorted(set(blockers))),
            execution_ledger_hash=_hash_mapping(execution_ledger),
            owner_release_hash=expected if decision_hash == expected else "",
        )
