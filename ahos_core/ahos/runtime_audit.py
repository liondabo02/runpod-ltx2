from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class RuntimeAuditReport:
    healthy: bool
    heartbeat_age_seconds: float | None
    service_state: str | None
    coding_counts: dict[str, int]
    department_counts: dict[str, int]
    blockers: tuple[str, ...]


class RuntimeAuditor:
    """Read-only health audit for one local AHOS runtime directory.

    The auditor never starts workers, changes queue state, approves work, or
    exposes provider credentials. It turns existing runtime evidence into a
    deterministic health report suitable for acceptance gates.
    """

    def __init__(self, runtime_dir: str | Path, *, heartbeat_max_age_seconds: float = 30.0) -> None:
        self.runtime_dir = Path(runtime_dir)
        if heartbeat_max_age_seconds <= 0:
            raise ValueError("heartbeat_max_age_seconds must be positive")
        self.heartbeat_max_age_seconds = float(heartbeat_max_age_seconds)

    def audit(self, *, now: datetime | None = None) -> RuntimeAuditReport:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        blockers: list[str] = []
        heartbeat_age: float | None = None
        service_state: str | None = None

        heartbeat_path = self.runtime_dir / "company-service-heartbeat.json"
        if not heartbeat_path.is_file():
            blockers.append("missing_heartbeat")
        else:
            try:
                heartbeat = _read_json(heartbeat_path)
                if not isinstance(heartbeat, dict):
                    raise ValueError("heartbeat must be an object")
                service_state = str(heartbeat.get("state") or "") or None
                heartbeat_at = _parse_timestamp(str(heartbeat["timestamp"]))
                heartbeat_age = max(0.0, (now - heartbeat_at).total_seconds())
                if heartbeat_age > self.heartbeat_max_age_seconds:
                    blockers.append("stale_heartbeat")
                if service_state in {"error", "stopped"}:
                    blockers.append(f"service_{service_state}")
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                blockers.append("invalid_heartbeat")

        coding_counts: dict[str, int] = {}
        queue_path = self.runtime_dir / "coding-supervisor-queue.json"
        if queue_path.is_file():
            try:
                queue = _read_json(queue_path)
                if not isinstance(queue, dict):
                    raise ValueError("coding queue must be an object")
                for item in queue.values():
                    if not isinstance(item, dict):
                        continue
                    status = str(item.get("status") or "unknown")
                    coding_counts[status] = coding_counts.get(status, 0) + 1
            except (OSError, ValueError, json.JSONDecodeError):
                blockers.append("invalid_coding_queue")
        else:
            blockers.append("missing_coding_queue")

        department_counts: dict[str, int] = {}
        department_path = self.runtime_dir / "department-service-status.json"
        if department_path.is_file():
            try:
                department = _read_json(department_path)
                if not isinstance(department, dict):
                    raise ValueError("department status must be an object")
                counts = department.get("counts") or {}
                if isinstance(counts, dict):
                    department_counts = {str(k): int(v) for k, v in counts.items()}
                if department.get("status") == "error":
                    blockers.append("department_service_error")
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                blockers.append("invalid_department_status")
        else:
            blockers.append("missing_department_status")

        config_path = self.runtime_dir / "company-service-config.json"
        if not config_path.is_file():
            blockers.append("missing_service_config")
        else:
            try:
                config = _read_json(config_path)
                if not isinstance(config, dict):
                    raise ValueError("config must be an object")
                coding = config.get("coding_supervisor")
                if not isinstance(coding, dict) or coding.get("enabled") is not True:
                    blockers.append("coding_supervisor_disabled")
                brain = config.get("holding_brain")
                if not isinstance(brain, dict) or brain.get("enabled") is not True:
                    blockers.append("holding_brain_disabled")
            except (OSError, ValueError, json.JSONDecodeError):
                blockers.append("invalid_service_config")

        # Exhausted items are important diagnostics but do not make the daemon
        # itself unhealthy; they remain visible in counts for owner review.
        return RuntimeAuditReport(
            healthy=not blockers,
            heartbeat_age_seconds=(round(heartbeat_age, 3) if heartbeat_age is not None else None),
            service_state=service_state,
            coding_counts=dict(sorted(coding_counts.items())),
            department_counts=dict(sorted(department_counts.items())),
            blockers=tuple(sorted(set(blockers))),
        )
