"""Read-only pre-deployment gate for AHOS.

Necessary checks only: a PASS is not a guarantee of fault-free production.
Never starts/stops services, sends model requests, alters queues or deploys code.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from .backup import verify_archive

REQUIRED_BACKUP_FILES = frozenset({
    "runtime/company-service.db",
    "runtime/owner-approvals.db",
    "runtime/worker-metrics.jsonl",
    "runtime/audit.jsonl",
    "runtime/taskboard.json",
})


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must contain UTC offset")
    return parsed.astimezone(timezone.utc)


def check_readiness(
    runtime_dir: str | Path,
    repository: str | Path,
    *,
    now: datetime | None = None,
    max_heartbeat_age_seconds: int = 300,
    min_delivery_rate: float = 0.90,
    require_test_receipt: bool = True,
) -> tuple[Check, ...]:
    """Inspect evidence without modifying the live system.

    A missing or malformed signal causes a FAIL rather than a guessed PASS.
    The test receipt must match the current code commit; external CI provenance
    and manual final approval remain required before actual deployment.
    """
    runtime = Path(runtime_dir)
    repo = Path(repository)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    checks: list[Check] = []

    state = None
    try:
        state = json.loads((runtime / "daemon-state.json").read_text(encoding="utf-8"))
        age = (now - _timestamp(state["last_tick_at"])).total_seconds()
        ok = state.get("status") == "running" and -60 <= age <= max_heartbeat_age_seconds
        checks.append(Check("daemon_heartbeat", ok, f"age_seconds={round(age, 1)} status={state.get('status')}"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        checks.append(Check("daemon_heartbeat", False, f"missing/invalid heartbeat: {type(exc).__name__}"))

    if state is None:
        checks.append(Check("delivery_quality", False, "missing runtime state"))
        checks.append(Check("real_delivery_evidence", False, "missing runtime state"))
    else:
        quality = state.get("quality") or {}
        rate = quality.get("delivery_rate")
        sample = quality.get("missions")
        ok = (isinstance(rate, (int, float)) and not isinstance(rate, bool)
              and isinstance(sample, int) and sample >= 30
              and 0 <= rate <= 1 and rate >= min_delivery_rate)
        checks.append(Check("delivery_quality", bool(ok), f"rate={rate} sample={sample} required>={min_delivery_rate}"))
        evidence = state.get("last_evidence") or {}
        files_changed = evidence.get("changed_files")
        proof = (
            evidence.get("evidence_ok") is True
            and evidence.get("source") == "filesystem"
            and evidence.get("proof_method") == "sha256"
            and evidence.get("filesystem_verified") is True
            and isinstance(files_changed, int)
            and not isinstance(files_changed, bool)
            and files_changed > 0
            and isinstance(evidence.get("productive_files"), int)
            and evidence.get("productive_files") > 0
            and evidence.get("removed_files") == 0
        )
        checks.append(Check(
            "real_delivery_evidence",
            proof,
            f"evidence_ok={evidence.get('evidence_ok')} changed_files={files_changed} "
            f"source={evidence.get('source')} method={evidence.get('proof_method')} "
            f"filesystem_verified={evidence.get('filesystem_verified')}",
        ))

    try:
        db = runtime / "company-service.db"
        # Do not open with the queue constructor: that could create/modify state.
        with sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=3) as conn:
            # Use a recent window, not lifetime counts. Mixed ISO/SQLite
            # timestamp formats cannot be ordered lexicographically.
            rows = conn.execute(
                "SELECT status FROM missions "
                "ORDER BY julianday(updated_at) DESC LIMIT 100"
            ).fetchall()
        counts = Counter(str(row[0]) for row in rows)
        blocked = counts["blocked"] + counts["failed"]
        completed = counts["completed"]
        cancelled = counts["cancelled"]
        terminal = blocked + completed + cancelled
        # Mass cancellation must never make blocked missions look successful.
        ok = (len(rows) >= 30 and completed >= 20 and terminal > 0
              and blocked / terminal <= 0.05
              and cancelled / terminal <= 0.10)
        checks.append(Check(
            "mission_queue", ok,
            f"recent={len(rows)} completed={completed} blocked_or_failed={blocked} "
            f"cancelled={cancelled} pending={counts['pending']} "
            "required: >=20 completed, <=5% blocked, <=10% cancelled",
        ))
    except (OSError, sqlite3.Error, ValueError) as exc:
        checks.append(Check("mission_queue", False, f"unreadable mission queue: {type(exc).__name__}"))

    archives = sorted((runtime / "backups").glob("runtime-*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not archives:
        checks.append(Check("verified_backup", False, "no runtime snapshot"))
    else:
        try:
            report = verify_archive(archives[0])
            with ZipFile(archives[0]) as bundle:
                names = set(bundle.namelist())
            missing = REQUIRED_BACKUP_FILES - names
            checks.append(Check(
                "verified_backup",
                not missing and report["schema"] == "ahos.runtime-backup.v2",
                f"schema={report['schema']} verified={report['verified_files']} missing_count={len(missing)}",
            ))
        except (OSError, KeyError, ValueError, BadZipFile) as exc:
            checks.append(Check("verified_backup", False, f"invalid/unverified backup: {type(exc).__name__}"))

    try:
        check = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        pending = len(check.stdout.splitlines())
        checks.append(Check("clean_source_tree", pending == 0, f"uncommitted_paths={pending}"))
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        checks.append(Check("clean_source_tree", False, f"git inspection failed: {type(exc).__name__}"))

    try:
        from .source_integrity import missing_tracked_imports

        missing = missing_tracked_imports(repo)
        checks.append(Check(
            "tracked_internal_imports",
            not missing,
            f"untracked_import_targets={len(missing)} examples={','.join(missing[:4])}",
        ))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        checks.append(Check(
            "tracked_internal_imports", False,
            f"source provenance audit failed: {type(exc).__name__}",
        ))

    if require_test_receipt:
        receipt_file = runtime / "release-test-receipt.json"
        try:
            receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
            rev = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout.strip()
            ok = (receipt.get("commit_sha") == rev and receipt.get("exit_code") == 0
                  and isinstance(receipt.get("passed"), int) and receipt["passed"] > 0
                  and receipt.get("failed") == 0 and receipt.get("trusted_ci") is True)
            checks.append(Check("trusted_test_receipt", bool(ok), f"matched_commit={receipt.get('commit_sha') == rev} tests_passed={receipt.get('passed')}"))
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            checks.append(Check("trusted_test_receipt", False, f"missing/invalid test receipt: {type(exc).__name__}"))

    return tuple(checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AHOS read-only production release gate")
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args(argv)
    checks = check_readiness(args.runtime_dir, args.repository)
    print(json.dumps({
        "ready_for_owner_review": all(check.ok for check in checks),
        "checks": [asdict(check) for check in checks],
    }, ensure_ascii=False, indent=2))
    return 0 if all(check.ok for check in checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
