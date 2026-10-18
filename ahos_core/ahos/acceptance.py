"""Immutable acceptance definition.

A project-supplied ``tools/check_offline.py`` is *not* trusted by itself: the
candidate could rewrite it. AHOS therefore pins the SHA-256 of the acceptance
gate the first time it accepts a project and refuses to run a modified gate.
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

    First call pins the current gate; later calls fail closed if it changed.
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
        baseline[key] = digest
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(
            json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True, "kabul tanımı sabitlendi (ilk kabul)", digest

    if stored != digest:
        return (
            False,
            "kabul tanımı değiştirilmiş: check_offline.py hash uyuşmuyor "
            f"({stored[:12]} != {digest[:12]})",
            digest,
        )
    return True, "kabul tanımı değişmemiş", digest
