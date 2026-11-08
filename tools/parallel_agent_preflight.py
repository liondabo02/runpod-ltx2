"""Read-only worktree collision preflight for simultaneous AHOS/DeepSeek agents.

No file contents or secrets are read; only Git path metadata is inspected.
No edits, locks, process changes, merges, deploys or paid network requests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, check=True, timeout=15,
    )
    return [
        part.decode("utf-8", "replace")
        for part in result.stdout.split(b"\0") if part
    ]


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, check=True, timeout=15, text=True,
    ).stdout.strip()


def _modified(repo: Path) -> set[str]:
    # Stable NUL-delimited paths even for unusual filenames.
    staged = set(_git(repo, "diff", "--cached", "--name-only", "-z"))
    unstaged = set(_git(repo, "diff", "--name-only", "-z"))
    untracked = set(_git(repo, "ls-files", "--others", "--exclude-standard", "-z"))
    return staged | unstaged | untracked


def _redact(name: str) -> str:
    normalized = name.casefold()
    if any(token in normalized for token in (
        ".env", "secret", "token", "credential", "private_key",
        ".pem", ".p12", ".pfx", "id_rsa",
    )):
        return "[sensitive path hidden]"
    return name


def analyze(live: str | Path, candidate: str | Path) -> dict[str, object]:
    active = Path(live).resolve()
    worktree = Path(candidate).resolve()
    if active == worktree:
        raise ValueError("live and candidate worktree must differ")
    common = subprocess.run(
        ["git", "-C", str(active), "merge-base", _head(active), _head(worktree)],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip()
    live_committed = set(_git(active, "diff", "--name-only", "-z", common, "HEAD"))
    candidate_committed = set(_git(worktree, "diff", "--name-only", "-z", common, "HEAD"))
    live_pending = _modified(active)
    candidate_pending = _modified(worktree)
    changed_candidate = candidate_committed | candidate_pending
    changed_live = live_committed | live_pending
    overlap = changed_candidate & changed_live
    # Summary never includes changed-file contents, raw diffs or credentials.
    return {
        "base": common[:12],
        "live_dirty_count": len(live_pending),
        "candidate_committed_change_count": len(candidate_committed),
        "candidate_dirty_count": len(candidate_pending),
        "overlap_count": len(overlap),
        "overlap_paths": sorted(set(_redact(name) for name in overlap))[:40],
        "requires_ownership_reconciliation": bool(overlap),
        "safe_to_merge_without_review": not bool(overlap) and not bool(live_pending),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AHOS multi-agent worktree collision scanner")
    parser.add_argument("--live", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.live, args.candidate)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}))
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0 if result["safe_to_merge_without_review"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
