from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class VerificationBaseline:
    verified_at: datetime
    commit_sha: str
    platform: str
    proofs: frozenset[str]

    def covers(self, capability: str, updated_at: str) -> bool:
        if capability not in self.proofs:
            return False
        try:
            event_at = _timestamp(updated_at)
        except (TypeError, ValueError):
            return False
        return event_at <= self.verified_at


def load_verification_baseline(path: str | Path) -> tuple[VerificationBaseline | None, str]:
    target = Path(path)
    if not target.is_file():
        return None, "missing"
    try:
        raw = json.loads(target.read_text(encoding="utf-8-sig"))
        if raw.get("schema") != "ahos.verification-baseline.v1":
            raise ValueError("unsupported schema")
        proofs_raw = raw.get("proofs")
        if not isinstance(proofs_raw, dict):
            raise ValueError("proofs must be an object")
        proofs = frozenset(str(name) for name, passed in proofs_raw.items() if passed is True)
        baseline = VerificationBaseline(
            verified_at=_timestamp(str(raw["verified_at"])),
            commit_sha=str(raw.get("commit_sha") or ""),
            platform=str(raw.get("platform") or "unknown"),
            proofs=proofs,
        )
        return baseline, "valid"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, "invalid"
