"""Immutable acceptance definition.

A project-supplied ``tools/check_offline.py`` is *not* trusted by itself: the
candidate could rewrite it. AHOS therefore pins the SHA-256 of the acceptance
gate ONCE, before the task starts (``acceptance_bootstrap.ensure_baseline``),
and refuses a gate that does not match the pin.

Verification is strictly read-only: if a project has no pre-authorized pin the
gate is refused ("önceden yetkilendirilmiş kabul kaydı yok"). It is never
pinned on the fly, because that would let a worker edit the acceptance test and
have the verifier authorize it in the same run.

Integrity (existence/hash) is not semantic correctness; it only guarantees the
acceptance definition did not change behind our back.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gate_path(root: str | Path) -> Path:
    return Path(root) / "tools" / "check_offline.py"


def trusted_gate(
    root: str | Path,
    baseline_path: str | Path,
) -> tuple[bool, str, str | None]:
    """Return (trusted, reason, digest).

    Read-only: never creates or rewrites the baseline. A missing pin is a
    refusal, not an implicit first acceptance.
    """

    gate = gate_path(root)
    if not gate.is_file():
        return False, "kabul testi yok (tools/check_offline.py)", None

    digest = _digest(gate)
    baseline_file = Path(baseline_path)
    try:
        baseline = (
            json.loads(baseline_file.read_text(encoding="utf-8"))
            if baseline_file.exists()
            else {}
        )
    except (OSError, json.JSONDecodeError):
        baseline = {}

    key = str(gate.resolve()).lower()
    stored = baseline.get(key)
    if stored is None:
        return False, "önceden yetkilendirilmiş kabul kaydı yok", None

    if stored != digest:
        return (
            False,
            "kabul tanımı değiştirilmiş: check_offline.py hash uyuşmuyor "
            f"({stored[:12]} != {digest[:12]})",
            digest,
        )
    return True, "kabul tanımı değişmemiş", digest
