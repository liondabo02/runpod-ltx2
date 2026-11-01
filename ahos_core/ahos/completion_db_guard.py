"""SQLite invariant: completion status must match a stored completion result.

Prevents direct raw SQL UPDATE/INSERT bypassing the mission queue API.
Existing legacy rows are NOT changed or reclassified by trigger installation.
This is necessary consistency protection, not independent artifact/QA proof.
"""

from __future__ import annotations

import sqlite3

_GUARD = """
    NEW.status = 'completed' AND CASE
      WHEN NEW.result_json IS NULL THEN 1
      WHEN json_valid(NEW.result_json) = 0 THEN 1
      WHEN COALESCE(json_extract(NEW.result_json, '$.status'), '') <> 'completed'
        THEN 1
      ELSE 0
    END
"""


def install_completion_guards(conn: sqlite3.Connection) -> None:
    """Idempotently install both update and insert guards within the caller DB.

    Requires SQLite JSON support. A missing feature is an explicit error,
    never a silent downgrade to an unguarded database.
    """
    conn.execute("SELECT json_valid(?)", ('{"status":"completed"}',)).fetchone()
    conn.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS ahos_completed_result_guard_update
        BEFORE UPDATE OF status, result_json ON missions
        WHEN {_GUARD}
        BEGIN
          SELECT RAISE(ABORT, 'ahos completed status requires consistent result_json');
        END
        """
    )
    conn.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS ahos_completed_result_guard_insert
        BEFORE INSERT ON missions
        WHEN {_GUARD}
        BEGIN
          SELECT RAISE(ABORT, 'ahos completed status requires consistent result_json');
        END
        """
    )
