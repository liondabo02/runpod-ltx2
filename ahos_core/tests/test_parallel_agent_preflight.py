"""Preflight accurately detects shared Git paths without reading file contents."""

from __future__ import annotations

import runpy
import subprocess
from pathlib import Path


def _command(*args):
    subprocess.run(args, capture_output=True, check=True)


def _prepare(tmp_path: Path):
    live = tmp_path / "live"
    live.mkdir()
    _command("git", "init", "-q", str(live))
    _command("git", "-C", str(live), "config", "user.email", "test@example.invalid")
    _command("git", "-C", str(live), "config", "user.name", "Test")
    (live / "shared.py").write_text("initial\n")
    (live / "only_candidate.py").write_text("initial\n")
    _command("git", "-C", str(live), "add", ".")
    _command("git", "-C", str(live), "commit", "-qm", "baseline")
    work = tmp_path / "candidate"
    _command("git", "-C", str(live), "worktree", "add", "-q", "-b", "candidate", str(work))
    return live, work


def _analyze():
    path = Path(__file__).resolve().parents[2] / "tools" / "parallel_agent_preflight.py"
    return runpy.run_path(str(path))["analyze"]


def test_detects_uncommitted_conflicts_in_both_worktrees(tmp_path):
    live, work = _prepare(tmp_path)
    (live / "shared.py").write_text("live changed\n")
    (work / "shared.py").write_text("candidate changed\n")
    (work / "only_candidate.py").write_text("candidate only\n")

    result = _analyze()(live, work)
    assert result["overlap_count"] == 1
    assert result["overlap_paths"] == ["shared.py"]
    assert result["requires_ownership_reconciliation"]
    assert not result["safe_to_merge_without_review"]


def test_reports_clean_separate_branches_as_safe(tmp_path):
    live, work = _prepare(tmp_path)
    (work / "only_candidate.py").write_text("new value\n")
    result = _analyze()(live, work)
    assert result["overlap_count"] == 0
    assert result["safe_to_merge_without_review"]


def test_secret_paths_are_not_exposed(tmp_path):
    live, work = _prepare(tmp_path)
    (live / "secret-token.txt").write_text("live key\n")
    (work / "secret-token.txt").write_text("work key\n")
    result = _analyze()(live, work)
    assert result["overlap_count"] == 1
    assert result["overlap_paths"] == ["[sensitive path hidden]"]
