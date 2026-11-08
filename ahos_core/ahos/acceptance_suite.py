"""Independent acceptance checks for a delivered change set.

A file diff is not verification. This module runs concrete checks on the files a
worker actually touched:

* the project's own quality gate (``tools/check_offline.py``) when present,
* ``node --check`` for changed JavaScript,
* ``python -m py_compile`` for changed Python,
* HTML files must still parse as markup (body/html markers).

Everything is bounded by a timeout and fail-closed: no check that ran means no
acceptance.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AcceptanceResult:
    ok: bool
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.checks:
            return "kabul komutu yok"
        failed = [f"{name}: {detail}" for name, ok, detail in self.checks if not ok]
        if failed:
            return "; ".join(failed)[:300]
        return f"{len(self.checks)} kontrol geçti"

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checks": [
                {"name": name, "ok": ok, "detail": detail}
                for name, ok, detail in self.checks
            ],
        }


def _run(argv: list[str], cwd: Path, timeout: float) -> tuple[bool, str]:
    import os

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError:
        return False, "araç bulunamadı"
    except subprocess.TimeoutExpired:
        return False, f"zaman aşımı ({timeout:.0f}s)"
    except OSError as exc:  # pragma: no cover - defensive
        return False, str(exc)
    detail = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode == 0, detail.splitlines()[-1][:200] if detail else ""


def run_acceptance(
    root: str | Path,
    changed_paths: list[str] | tuple[str, ...],
    *,
    timeout: float = 60.0,
) -> AcceptanceResult:
    project = Path(root)
    checks: list[tuple[str, bool, str]] = []

    gate = project / "tools" / "check_offline.py"
    if gate.is_file():
        ok, detail = _run([sys.executable, str(gate)], project, timeout)
        checks.append(("kalite kapısı", ok, detail))
    else:
        checks.append(("kalite kapısı", False, "tools/check_offline.py yok"))

    for relative in changed_paths:
        path = project / relative
        if not path.is_file():
            checks.append((relative, False, "dosya bulunamadı"))
            continue
        suffix = path.suffix.lower()
        if suffix in {".js", ".mjs", ".cjs"}:
            ok, detail = _run(["node", "--check", str(path)], project, timeout)
            checks.append((f"node --check {relative}", ok, detail))
        elif suffix == ".py":
            ok, detail = _run(
                [sys.executable, "-m", "py_compile", str(path)], project, timeout
            )
            checks.append((f"py_compile {relative}", ok, detail))
        elif suffix in {".html", ".htm"}:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            ok = "<html" in text and "</html>" in text
            checks.append((f"html {relative}", ok, "html/body işaretleri"))

    ok = bool(checks) and all(item[1] for item in checks)
    return AcceptanceResult(ok=ok, checks=checks)
