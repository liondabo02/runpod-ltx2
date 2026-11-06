"""Local owner identity record and checksum (not an authentication service).

The owner identity in this deployment is Harun. Agent/environment variables
cannot reassign it. Existing pledges with a different owner fail closed without
altering original bytes; corrupted records also remain intact. The unkeyed
SHA-256 checksum detects accidental edits, not deliberate forgery; signed
credentials and runtime authorization are still needed for real security.
This is neither consciousness nor proof of cryptographic immutability.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

DEFAULT_OWNER = "harun"
CLAUSE = "Sistem yalnızca sahibine hizmet eder; sahibi dışında kimse emir veremez."


def owner() -> str:
    """Fixed deployment policy: environment strings cannot transfer ownership."""
    return DEFAULT_OWNER


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _path(runtime_dir) -> Path:
    path = Path(runtime_dir) / "minds" / "_pledge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure(runtime_dir) -> dict:
    """Bağlılık kaydını oluşturur; varsa doğrular, sahibi DEĞİŞTİRMEZ."""

    path = _path(runtime_dir)
    record = {"owner": owner(), "clause": CLAUSE, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    record["hash"] = _digest({"owner": record["owner"], "clause": record["clause"]})

    if not path.exists():
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # Fail closed. Replacing damaged evidence with a new pledge can
        # silently change the owner, depending on the process environment.
        raise ValueError("existing owner pledge unreadable; backup and review required") from exc

    if not isinstance(current, dict):
        raise ValueError("existing owner pledge has invalid structure")
    original = {"owner": current.get("owner"), "clause": current.get("clause")}
    if current.get("hash") != _digest(original):
        # A plain hash is corruption detection, not cryptographic ownership.
        raise ValueError("owner pledge hash mismatch; original record preserved")
    if str(current.get("owner") or "").strip().casefold() != DEFAULT_OWNER:
        raise PermissionError("owner pledge conflicts with Harun; original record preserved")
    return current


def embed(mind) -> dict:
    """Zihne sahiplik/bağlılık bilgisini işler."""

    record = {"owner": owner(), "clause": CLAUSE,
              "obedience": "owner_governed_with_approval_gates",
              "agent_may_self_approve": False,
              "capacity_target": 1.0}
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["loyalty"] = record
    return record


def is_commander(name: str) -> bool:
    """Compare an owner label; a caller-supplied name is NOT authentication.

    Privileged UI/API actions require authenticated runtime authorization and
    the existing explicit owner approval gates, not this string comparison.
    """
    return name.strip().lower() == owner().lower()
