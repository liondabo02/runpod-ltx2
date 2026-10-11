from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditIntegrityError(RuntimeError):
    """Raised when the append-only audit journal fails integrity verification."""


@dataclass(frozen=True, slots=True)
class AuditEvent:
    schema_version: int
    sequence: int
    event_id: str
    timestamp: str
    event_type: str
    correlation_id: str
    payload: dict[str, Any]
    previous_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only, tamper-evident JSONL audit journal for AHOS."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _raw_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditIntegrityError(
                    f"Invalid JSON in audit journal at line {line_number}."
                ) from exc
            if not isinstance(record, dict):
                raise AuditIntegrityError(
                    f"Audit journal line {line_number} is not a JSON object."
                )
            records.append(record)
        return records

    @staticmethod
    def _legacy_hash(record: dict[str, Any]) -> str:
        """Hash pre-v1 records so new records can safely chain after them."""
        return _sha256(record)

    def _tail_state(self) -> tuple[int, str | None]:
        records = self._raw_records()
        if not records:
            return 1, None

        last = records[-1]
        if (
            last.get("schema_version") == self.SCHEMA_VERSION
            and isinstance(last.get("sequence"), int)
            and isinstance(last.get("event_id"), str)
        ):
            return int(last["sequence"]) + 1, str(last["event_id"])

        return len(records) + 1, self._legacy_hash(last)

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        timestamp: str | None = None,
    ) -> AuditEvent:
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary.")

        sequence, previous_hash = self._tail_state()
        normalized_correlation_id = (
            correlation_id
            or str(payload.get("correlation_id") or "")
            or "local"
        )
        normalized_timestamp = timestamp or datetime.now(timezone.utc).isoformat()

        body = {
            "schema_version": self.SCHEMA_VERSION,
            "sequence": sequence,
            "timestamp": normalized_timestamp,
            "event_type": event_type.strip(),
            "correlation_id": normalized_correlation_id,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_id = _sha256(body)

        event = AuditEvent(
            schema_version=self.SCHEMA_VERSION,
            sequence=sequence,
            event_id=event_id,
            timestamp=normalized_timestamp,
            event_type=event_type.strip(),
            correlation_id=normalized_correlation_id,
            payload=payload,
            previous_hash=previous_hash,
        )

        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(_canonical_json(event.to_dict()) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

        return event

    def records(self) -> list[dict[str, Any]]:
        """Return a snapshot of all journal records without mutating the journal."""
        return self._raw_records()

    def verify_integrity(self) -> bool:
        """Verify sequence numbers, event hashes and the append-only hash chain."""
        previous_hash: str | None = None

        for index, record in enumerate(self._raw_records(), start=1):
            if record.get("schema_version") != self.SCHEMA_VERSION:
                previous_hash = self._legacy_hash(record)
                continue

            required = {
                "schema_version",
                "sequence",
                "event_id",
                "timestamp",
                "event_type",
                "correlation_id",
                "payload",
                "previous_hash",
            }
            missing = required.difference(record)
            if missing:
                raise AuditIntegrityError(
                    f"Audit record {index} is missing fields: {sorted(missing)}"
                )

            if record["sequence"] != index:
                raise AuditIntegrityError(
                    f"Audit record {index} has sequence {record['sequence']}."
                )

            if record["previous_hash"] != previous_hash:
                raise AuditIntegrityError(
                    f"Audit record {index} has an invalid previous_hash."
                )

            body = {
                "schema_version": record["schema_version"],
                "sequence": record["sequence"],
                "timestamp": record["timestamp"],
                "event_type": record["event_type"],
                "correlation_id": record["correlation_id"],
                "payload": record["payload"],
                "previous_hash": record["previous_hash"],
            }
            expected_id = _sha256(body)
            if record["event_id"] != expected_id:
                raise AuditIntegrityError(
                    f"Audit record {index} failed hash verification."
                )

            previous_hash = record["event_id"]

        return True
