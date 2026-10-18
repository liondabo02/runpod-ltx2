from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from .proof_evidence import ProofEvidence


@dataclass(frozen=True, slots=True)
class ProofManifest:
    schema: str
    commit_sha: str
    platform: str
    evidence: tuple[dict[str, object], ...]
    manifest_sha256: str


def build_manifest(rows: Iterable[ProofEvidence]) -> ProofManifest:
    evidence_rows = tuple(rows)
    if not evidence_rows:
        raise ValueError("evidence is required")
    commits = {row.commit_sha for row in evidence_rows}
    platforms = {row.platform for row in evidence_rows}
    if len(commits) != 1 or len(platforms) != 1:
        raise ValueError("manifest evidence must share one commit and platform")

    payload_rows = tuple(
        {
            **asdict(row),
            "observed_at": row.observed_at.isoformat(),
        }
        for row in sorted(evidence_rows, key=lambda item: item.kind)
    )
    core = {
        "schema": "ahos.proof-manifest.v1",
        "commit_sha": next(iter(commits)),
        "platform": next(iter(platforms)),
        "evidence": payload_rows,
    }
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return ProofManifest(
        schema=core["schema"],
        commit_sha=core["commit_sha"],
        platform=core["platform"],
        evidence=payload_rows,
        manifest_sha256=digest,
    )
