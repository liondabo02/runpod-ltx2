from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory


@dataclass(frozen=True, slots=True)
class StateIntegrityReport:
    json_corruption_detected: bool
    hash_tamper_detected: bool
    sqlite_integrity_ok: bool
    sqlite_corruption_detected: bool
    passed: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_state_integrity_rehearsal() -> StateIntegrityReport:
    with TemporaryDirectory(prefix="ahos-q99-integrity-") as tmp:
        root = Path(tmp)

        json_path = root / "queue.json"
        json_path.write_text(json.dumps({"tasks":{"A":{"status":"queued"}}}), encoding="utf-8")
        expected_hash = _sha256(json_path)
        json_path.write_text('{"tasks":', encoding="utf-8")
        try:
            json.loads(json_path.read_text(encoding="utf-8"))
            json_corrupt = False
        except json.JSONDecodeError:
            json_corrupt = True
        hash_tamper = _sha256(json_path) != expected_hash

        db_path = root / "state.sqlite3"
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO items(value) VALUES ('ok')")
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

        raw = bytearray(db_path.read_bytes())
        if len(raw) < 200:
            raise AssertionError("unexpectedly small sqlite file")
        # Damage the SQLite header in the isolated copy.
        raw[0:16] = b"X" * 16
        broken = root / "broken.sqlite3"
        broken.write_bytes(raw)
        broken_db = None
        try:
            broken_db = sqlite3.connect(broken)
            broken_db.execute("PRAGMA integrity_check").fetchone()
            sqlite_corrupt = False
        except sqlite3.DatabaseError:
            sqlite_corrupt = True
        finally:
            if broken_db is not None:
                broken_db.close()

        return StateIntegrityReport(
            json_corruption_detected=json_corrupt,
            hash_tamper_detected=hash_tamper,
            sqlite_integrity_ok=integrity,
            sqlite_corruption_detected=sqlite_corrupt,
            passed=json_corrupt and hash_tamper and integrity and sqlite_corrupt,
        )
