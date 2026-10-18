from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DashboardFlowReport:
    accepted: bool
    blockers: tuple[str, ...]


class DashboardFlowEvidence:
    """Validate an isolated dashboard create-and-render critical flow."""

    def evaluate(self, payload: Mapping[str, object]) -> DashboardFlowReport:
        blockers: list[str] = []
        required = {
            "task_id", "task_status", "task_attempts", "post_status",
            "html_has_task_id", "html_has_task_title",
            "screenshot_sha256", "screenshot_size_bytes",
            "isolated_runtime", "unique_port", "server_terminated",
        }
        blockers.extend(f"missing:{name}" for name in sorted(required - set(payload)))
        if payload.get("post_status") != 200:
            blockers.append("post_not_200")
        if payload.get("task_status") != "queued":
            blockers.append("task_not_queued")
        if payload.get("task_attempts") != 0:
            blockers.append("worker_execution_detected")
        if payload.get("html_has_task_id") is not True:
            blockers.append("task_id_missing_from_dashboard")
        if payload.get("html_has_task_title") is not True:
            blockers.append("task_title_missing_from_dashboard")
        digest = str(payload.get("screenshot_sha256") or "")
        if len(digest) != 64:
            blockers.append("invalid_screenshot_hash")
        if int(payload.get("screenshot_size_bytes") or 0) < 1000:
            blockers.append("screenshot_too_small")
        if payload.get("isolated_runtime") is not True:
            blockers.append("runtime_not_isolated")
        if payload.get("unique_port") is not True:
            blockers.append("port_not_isolated")
        if payload.get("server_terminated") is not True:
            blockers.append("server_not_terminated")
        return DashboardFlowReport(not blockers, tuple(sorted(set(blockers))))
