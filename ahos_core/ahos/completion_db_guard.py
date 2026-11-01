"""SQLite invariant (stage 2): a completed mission must carry a verified delivery.

1. Status/result consistency: `status='completed'` requires a result document
   whose own status is `completed` and whose steps array is non-empty.
2. Verified delivery record: the result must contain
   `delivery.verified = 1` and at least one `delivery.qa_worker_ids` entry.
   When the mission has steps, there must be exactly one QA id per step.

Per-step independence (qa id != producer id) and the single-shot QA identity
are enforced by the queue API (`PersistentMissionQueue.complete`) and encoded
in `delivery.verified`; the trigger makes the record mandatory for every
writer, including ad-hoc SQL.

Existing legacy rows are NOT changed or reclassified by trigger installation.
"""

from __future__ import annotations

import sqlite3

_GUARD = """
    NEW.status = 'completed' AND (
      NEW.result_json IS NULL
      OR json_valid(NEW.result_json) = 0
      OR COALESCE(json_extract(NEW.result_json, '$.status'), '') <> 'completed'
      OR COALESCE(json_type(NEW.result_json, '$.steps'), '') <> 'array'
      OR COALESCE(json_extract(NEW.result_json, '$.delivery.verified'), 0) <> 1
      OR COALESCE(json_type(NEW.result_json, '$.delivery.qa_worker_ids'), '') <> 'array'
      OR COALESCE(json_array_length(NEW.result_json, '$.delivery.qa_worker_ids'), 0) < 1
      OR (
           json_array_length(NEW.result_json, '$.steps') > 0
           AND json_array_length(NEW.result_json, '$.delivery.qa_worker_ids')
               <> json_array_length(NEW.result_json, '$.steps')
         )
    )
"""

_MESSAGE = (
    "ahos completed status requires a consistent result_json and a verified "
    "delivery record (independent qa_worker_ids for every step)"
)


def install_completion_guards(conn: sqlite3.Connection) -> None:
    """Install (or upgrade) both guards within the caller DB.

    Triggers are dropped and recreated so an older, weaker guard is replaced
    instead of silently kept. Requires SQLite JSON support; a missing feature
    is an explicit error, never a silent downgrade to an unguarded database.
    """
    conn.execute("SELECT json_valid(?)", ('{"status":"completed"}',)).fetchone()

    for name, clause in (
        ("ahos_completed_result_guard_update", "UPDATE OF status, result_json ON missions"),
        ("ahos_completed_result_guard_insert", "INSERT ON missions"),
    ):
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.execute(
            f"""
            CREATE TRIGGER {name}
            BEFORE {clause}
            WHEN {_GUARD}
            BEGIN
              SELECT RAISE(ABORT, '{_MESSAGE}');
            END
            """
        )
