"""Durable queue ownership and crash recovery.

A mission can end up owned by nobody: the worker crashed, the lease expired, or
the process was killed mid-run. Left alone, such a row blocks the same objective
forever, which is exactly how the holding silently stops.

This module repairs those rows in place, with hard caps so a permanently broken
mission cannot loop. It only touches the mission queue schema; the owning
classes stay unchanged.
"""

from __future__ import annotations

import time
from pathlib import Path

STUCK_ERROR = "kurtarma: sahipsiz görev yeniden açıldı"
LEASE_ERROR = "kurtarma: süresi geçen kira geri alındı"


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def recover(
    queue,
    *,
    now: float | None = None,
    reopen_limit: int = 20,
    attempts_cap: int = 3,
) -> dict:
    """Reclaim expired leases and reopen missions stuck below the retry cap.

    Returns counts so the caller can put them in a heartbeat or an audit line.
    """

    now = time.time() if now is None else now
    if reopen_limit < 1 or attempts_cap < 1:
        raise ValueError("recovery limits must be positive")
    stamp = _utc_now()
    report = {"expired_leases": 0, "reopened_stuck": 0, "gave_up": 0}

    with queue._connect() as conn:  # noqa: SLF001 - same package, additive use
        cursor = conn.execute(
            """
            UPDATE missions
            SET status='pending', lease_owner=NULL, lease_until=NULL,
                updated_at=?, last_error=COALESCE(last_error, ?)
            WHERE status='running'
              AND lease_until IS NOT NULL AND lease_until < ?
            """,
            (stamp, LEASE_ERROR, now),
        )
        report["expired_leases"] = int(cursor.rowcount or 0)

        rows = conn.execute(
            """
            SELECT mission_id, attempts, max_attempts
            FROM missions
            WHERE status='pending' AND next_attempt_at <= ? AND attempts >= max_attempts
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (now, reopen_limit),
        ).fetchall()

        for row in rows:
            attempts = int(row["attempts"] or 0)
            if attempts >= attempts_cap:
                conn.execute(
                    """
                    UPDATE missions
                    SET status='blocked', updated_at=?, last_error=?
                    WHERE mission_id=?
                    """,
                    (stamp, "kurtarma: deneme sınırı aşıldı", row["mission_id"]),
                )
                report["gave_up"] += 1
                continue
            conn.execute(
                """
                UPDATE missions
                SET attempts=0, max_attempts=?, next_attempt_at=0,
                    lease_owner=NULL, lease_until=NULL, updated_at=?, last_error=?
                WHERE mission_id=?
                """,
                (
                    min(attempts_cap, max(attempts + 1, int(row["max_attempts"] or 1) + 1)),
                    stamp,
                    STUCK_ERROR,
                    row["mission_id"],
                ),
            )
            report["reopened_stuck"] += 1

    return report


def recover_file(path: str | Path, **kwargs) -> dict:
    """Convenience for CLI/daemon use: open the queue file and recover."""

    from .autonomous_company import PersistentMissionQueue

    queue = PersistentMissionQueue(Path(path))
    return recover(queue, **kwargs)


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    path = "runtime/company-service.db"
    if "--db" in args and args.index("--db") + 1 < len(args):
        path = args[args.index("--db") + 1]
    report = recover_file(path)
    print(
        "kurtarma: süresi geçen kira={expired_leases}, yeniden açılan={reopened_stuck}, "
        "vazgeçilen={gave_up}".format(**report)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
