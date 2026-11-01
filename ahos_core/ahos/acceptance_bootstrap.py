"""Pin a project's acceptance gate before the first QA run.

The QA layer refuses a gate it has not seen before ("önceden yetkilendirilmiş
kabul kaydı yok"), which is correct for tamper detection but blocks the very
first delivery of a project. This bootstrap records the pin once, atomically,
using the same format and the same safety checks (no symlinks, size limit).

Later changes to the gate still fail the hash comparison, so the protection is
preserved.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

MAX_GATE_BYTES = 1024 * 1024


def _gate_provenance(root: Path, gate: Path) -> tuple[bool, str]:
    """Pin only a gate whose provenance is known.

    - Git project: the gate must be tracked and unmodified (working tree and
      index), so a worker cannot rewrite the acceptance test and then have the
      bootstrap pin the tampered file.
    - Non-git project: allowed only with the explicit owner opt-in
      ``AHOS_ACCEPTANCE_ALLOW_UNTRACKED=1``.
    """

    if not (root / ".git").exists():
        opt_in = os.environ.get("AHOS_ACCEPTANCE_ALLOW_UNTRACKED", "0").strip().lower()
        if opt_in in {"1", "true", "yes", "on"}:
            return True, "sürüm kontrolü yok (sahip izniyle)"
        return False, "kabul testi sürüm kontrolünde değil (AHOS_ACCEPTANCE_ALLOW_UNTRACKED=1 gerekli)"

    rel = gate.relative_to(root).as_posix()
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", rel],
            capture_output=True, timeout=15,
        )
        if tracked.returncode != 0:
            return False, "kabul testi sürüm kontrolüne eklenmemiş"
        for args, label in (
            (["git", "-C", str(root), "diff", "--quiet", "--", rel], "çalışma ağacında değişmiş"),
            (["git", "-C", str(root), "diff", "--cached", "--quiet", "--", rel], "hazırlık alanında değişmiş"),
        ):
            result = subprocess.run(args, capture_output=True, timeout=15)
            if result.returncode != 0:
                return False, f"kabul testi {label}"
    except (OSError, subprocess.SubprocessError):
        return False, "kabul testinin sürüm durumu denetlenemedi"
    return True, "kabul testi sürüm kontrolünde temiz"


def ensure_baseline(project_root: str | Path, evidence_root: str | Path) -> tuple[bool, str]:
    """Create the acceptance baseline if missing; never overwrite an existing one."""

    root = Path(project_root).resolve()
    gate = root / "tools" / "check_offline.py"
    baseline = Path(evidence_root) / "acceptance-baseline.json"

    if baseline.is_file() and not baseline.is_symlink():
        return True, "kabul kaydı zaten var"
    if gate.is_symlink() or gate.parent.is_symlink() or not gate.is_file():
        return False, "kabul testi yok veya güvenli dosya değil"
    clean, why = _gate_provenance(root, gate.resolve())
    if not clean:
        return False, why
    try:
        gate.resolve().relative_to(root)
        if gate.stat().st_size > MAX_GATE_BYTES:
            return False, "kabul testi boyut sınırını aşıyor"
        digest = hashlib.sha256(gate.read_bytes()).hexdigest()
        entries: dict[str, str] = {}
        if baseline.is_file():
            try:
                loaded = json.loads(baseline.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    entries = {
                        str(key): str(value)
                        for key, value in loaded.items()
                        if isinstance(key, str) and isinstance(value, str)
                    }
            except (OSError, ValueError):
                entries = {}
        entries[str(gate.resolve()).lower()] = digest
        baseline.parent.mkdir(parents=True, exist_ok=True)
        temporary = baseline.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        temporary.replace(baseline)
        return True, "kabul testi sabitlendi"
    except (OSError, ValueError) as exc:
        return False, f"kabul kaydı yazılamadı: {type(exc).__name__}"
