"""Ownership guard: refuse commits that would collide with another agent's area.

Two things are enforced:

1. **Forbidden paths** — the Codex-owned control-plane runtime and cloud releases
   are never touched by this workspace.
2. **Shared files** — a small set of files both agents legitimately need. Edits
   are allowed but reported, so the author double-checks the diff and the tests.

Install as a pre-commit hook with ``python tools/check_ownership.py --install``.
Exit code 1 blocks the commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FORBIDDEN = (
    "control_plane_v2/runtime/AHOS-QUALITY-99",
    "ahos-quality-99/releases",
)

SHARED = (
    "ahos_core/pyproject.toml",
    "ahos_core/ahos/owner_console.py",
    "ahos_core/ahos/autonomy.py",
    "ahos_core/ahos/daemon.py",
    "ahos_core/ahos/acceptance.py",
    "ahos_core/ahos/project_qa.py",
    "ahos_core/ahos/autonomous_company.py",
    "control_plane_v2/AHOS-Daemon.ps1",
    "control_plane_v2/AHOS-Watchdog.ps1",
)

HOOK = """#!/bin/sh
# AHOS ownership guard: blocks commits that touch another agent's area.
python "C:/actions-runner/_work/runpod-ltx2/runpod-ltx2/tools/check_ownership.py" || exit 1
"""


def staged_files() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def check(files: list[str]) -> tuple[list[str], list[str]]:
    blocked = [item for item in files if any(item.startswith(path) for path in FORBIDDEN)]
    shared = [item for item in files if item in SHARED]
    return blocked, shared


def install_hook() -> int:
    root = Path(__file__).resolve().parents[1]
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text(HOOK.replace("\n", "\r\n" if sys.platform == "win32" else "\n"), encoding="utf-8")
    print(f"kanca kuruldu: {hook}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    if "--install" in args:
        return install_hook()
    files = args or staged_files()
    if not files:
        print("sahiplik denetimi: değişiklik yok")
        return 0
    blocked, shared = check(files)
    if blocked:
        print("ENGELLENDİ — başka ajanın alanına dokunuluyor:")
        for item in blocked:
            print(f"  ✗ {item}")
        return 1
    print(f"sahipli k: temiz ({len(files)} dosya)")
    if shared:
        print("paylaşılan dosyalar (diff ve testleri iki kez kontrol et):")
        for item in shared:
            print(f"  ! {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
