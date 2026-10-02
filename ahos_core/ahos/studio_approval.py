from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


class StudioApprovalError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StudioDecisionResult:
    episode_id: str
    decision: str
    decision_path: Path
    execution_authorized: bool
    max_budget_usd: float


def _stable_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StudioApprovalError(f"required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StudioApprovalError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StudioApprovalError(f"expected a JSON object in {path}")
    return payload


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _validate_approval_packet(
    studio: Path,
) -> tuple[dict[str, object], str, dict[str, str]]:
    approval_path = studio / "OWNER-APPROVAL.json"
    approval = _read_object(approval_path)
    if approval.get("schema") != "ahos.single-owner-decision.v1":
        raise StudioApprovalError("unsupported owner approval packet schema")
    episode_id = str(approval.get("episode_id") or "").strip()
    if not episode_id:
        raise StudioApprovalError("approval packet has no episode_id")
    expected_evidence_hash = str(approval.get("evidence_hash") or "")
    unsigned = dict(approval)
    unsigned.pop("evidence_hash", None)
    if not expected_evidence_hash or _hash(unsigned) != expected_evidence_hash:
        raise StudioApprovalError("approval packet integrity check failed")
    if approval.get("owner_approved") is not False:
        raise StudioApprovalError("approval request must remain immutable and unapproved")

    artifacts = approval.get("artifacts")
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise StudioApprovalError("approval packet has no artifact manifest")
    studio_root = studio.resolve()
    artifact_hashes: dict[str, str] = {}
    for name, relative in artifacts.items():
        candidate = (studio_root / str(relative)).resolve()
        try:
            candidate.relative_to(studio_root)
        except ValueError as exc:
            raise StudioApprovalError(
                f"artifact {name!r} escapes the studio directory"
            ) from exc
        if not candidate.is_file():
            raise StudioApprovalError(f"artifact {name!r} is missing: {candidate}")
        artifact_hashes[str(name)] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return (
        approval,
        hashlib.sha256(approval_path.read_bytes()).hexdigest(),
        artifact_hashes,
    )


def record_owner_decision(
    studio_directory: str | Path,
    *,
    decision: str,
    confirm_episode_id: str,
    max_budget_usd: float = 0.0,
    owner_id: str = "harun",
) -> StudioDecisionResult:
    """Record one hash-bound decision without performing any external action."""
    studio = Path(studio_directory)
    approval, request_file_hash, artifact_hashes = _validate_approval_packet(studio)
    episode_id = str(approval["episode_id"])
    normalized = decision.strip().lower()
    if normalized not in {"approve", "reject"}:
        raise StudioApprovalError("decision must be 'approve' or 'reject'")
    if confirm_episode_id.strip() != episode_id:
        raise StudioApprovalError(
            f"confirmation must exactly match episode_id {episode_id!r}"
        )
    if not owner_id.strip():
        raise StudioApprovalError("owner_id must not be empty")
    if max_budget_usd < 0:
        raise StudioApprovalError("max_budget_usd must not be negative")
    if normalized == "approve" and max_budget_usd <= 0:
        raise StudioApprovalError(
            "approval requires a positive max_budget_usd safety ceiling"
        )
    if normalized == "reject" and max_budget_usd != 0:
        raise StudioApprovalError("a rejected decision must have zero budget")

    decision_path = studio / "OWNER-DECISION.json"
    authorization = normalized == "approve"
    payload: dict[str, object] = {
        "schema": "ahos.owner-decision-receipt.v1",
        "episode_id": episode_id,
        "decision": normalized,
        "owner_id": owner_id.strip(),
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "approval_request_sha256": request_file_hash,
        "evidence_hash": approval["evidence_hash"],
        "artifact_sha256": artifact_hashes,
        "max_budget_usd": round(float(max_budget_usd), 6),
        "owner_approved": authorization,
        "paid_execution_enabled": authorization,
        "external_execution_enabled": authorization,
        "publishing_enabled": False,
        "consumed": False,
    }
    payload["decision_hash"] = _hash(payload)

    if decision_path.exists():
        existing = _read_object(decision_path)
        existing_hash = str(existing.get("decision_hash") or "")
        unsigned_existing = dict(existing)
        unsigned_existing.pop("decision_hash", None)
        if not existing_hash or _hash(unsigned_existing) != existing_hash:
            raise StudioApprovalError("existing owner decision integrity check failed")
        comparable = {
            key: existing.get(key)
            for key in (
                "episode_id",
                "decision",
                "owner_id",
                "approval_request_sha256",
                "evidence_hash",
                "artifact_sha256",
                "max_budget_usd",
                "owner_approved",
                "paid_execution_enabled",
                "external_execution_enabled",
                "publishing_enabled",
            )
        }
        requested = {key: payload[key] for key in comparable}
        if comparable != requested:
            raise StudioApprovalError(
                "a different owner decision already exists; decisions are immutable"
            )
        payload = existing
    else:
        _atomic_write(decision_path, payload)

    report_path = studio / "studio-report.json"
    report = _read_object(report_path)
    report.update(
        {
            "status": "approved_for_execution"
            if authorization
            else "rejected_by_owner",
            "owner_action_count": 0,
            "owner_decision": decision_path.name,
            "release_ready": False,
        }
    )
    _atomic_write(report_path, report)
    return StudioDecisionResult(
        episode_id=episode_id,
        decision=normalized,
        decision_path=decision_path,
        execution_authorized=authorization,
        max_budget_usd=float(payload["max_budget_usd"]),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record a tamper-evident owner decision for one studio episode"
    )
    parser.add_argument("--studio-dir", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--approve", action="store_true")
    group.add_argument("--reject", action="store_true")
    parser.add_argument("--confirm-episode", required=True)
    parser.add_argument("--max-budget-usd", type=float, default=0.0)
    parser.add_argument("--owner-id", default="harun")
    args = parser.parse_args(argv)
    result = record_owner_decision(
        args.studio_dir,
        decision="approve" if args.approve else "reject",
        confirm_episode_id=args.confirm_episode,
        max_budget_usd=args.max_budget_usd,
        owner_id=args.owner_id,
    )
    print(
        json.dumps(
            {
                "episode_id": result.episode_id,
                "decision": result.decision,
                "execution_authorized": result.execution_authorized,
                "max_budget_usd": result.max_budget_usd,
                "decision_receipt": str(result.decision_path),
                "external_calls_made": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
