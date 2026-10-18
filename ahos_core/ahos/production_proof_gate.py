from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .proof_evidence import ProofEvidence, REQUIRED_PROOF_KINDS, is_fresh, verify_artifact
from .verification_baseline import VerificationBaseline


@dataclass(frozen=True, slots=True)
class ProofBundleReport:
    ready: bool
    proven: frozenset[str]
    blockers: tuple[str, ...]
    commit_sha: str
    platform: str


class ProductionProofGate:
    """Strict evidence gate for AHOS 99% readiness.

    Evidence must be fresh, hash-verified, tied to the same commit/platform, and
    explicitly passed. The gate never fabricates a proof from source code,
    documentation, or unit-test presence alone.
    """

    def __init__(self, *, max_age_seconds: float = 86400.0) -> None:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        self.max_age_seconds = float(max_age_seconds)

    def evaluate(
        self,
        evidence_rows: Iterable[ProofEvidence],
        *,
        root: str | Path = ".",
        now: datetime | None = None,
    ) -> ProofBundleReport:
        rows = tuple(evidence_rows)
        blockers: list[str] = []
        proven: set[str] = set()

        if not rows:
            return ProofBundleReport(
                ready=False,
                proven=frozenset(),
                blockers=("no_evidence",),
                commit_sha="",
                platform="",
            )

        commits = {row.commit_sha for row in rows}
        platforms = {row.platform for row in rows}
        if len(commits) != 1:
            blockers.append("mixed_commit_evidence")
        if len(platforms) != 1:
            blockers.append("mixed_platform_evidence")

        current = now or datetime.now(timezone.utc)
        for row in rows:
            if not row.passed:
                blockers.append(f"{row.kind}:failed")
                continue
            ok, reason = verify_artifact(row, root=root)
            if not ok:
                blockers.append(f"{row.kind}:{reason}")
                continue
            if not is_fresh(row, max_age_seconds=self.max_age_seconds, now=current):
                blockers.append(f"{row.kind}:stale")
                continue
            proven.add(row.kind)

        missing = REQUIRED_PROOF_KINDS - proven
        blockers.extend(f"{kind}:missing" for kind in sorted(missing))
        unique = tuple(sorted(set(blockers)))
        commit_sha = next(iter(commits)) if len(commits) == 1 else ""
        platform = next(iter(platforms)) if len(platforms) == 1 else ""
        return ProofBundleReport(
            ready=not unique,
            proven=frozenset(proven),
            blockers=unique,
            commit_sha=commit_sha,
            platform=platform,
        )

    def to_verification_baseline(
        self,
        report: ProofBundleReport,
        *,
        verified_at: datetime | None = None,
        extra_proofs: Iterable[str] = (),
    ) -> VerificationBaseline:
        if not report.ready:
            raise ValueError("proof bundle is not ready")
        proofs = set(report.proven)
        proofs.update(extra_proofs)
        return VerificationBaseline(
            verified_at=(verified_at or datetime.now(timezone.utc)).astimezone(timezone.utc),
            commit_sha=report.commit_sha,
            platform=report.platform,
            proofs=frozenset(proofs),
        )
