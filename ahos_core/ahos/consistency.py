from __future__ import annotations

from dataclasses import dataclass

from .autonomous_company import PersistentMissionQueue, QueueStatus
from .owner_approval import ApprovalStatus, OwnerApprovalInbox


@dataclass(frozen=True, slots=True, order=True)
class ConsistencyDiagnostic:
    code: str
    mission_id: str
    detail: str


class MissionQueueConsistencyChecker:
    """Read-only consistency checks across missions and owner approvals."""

    def __init__(self, queue: PersistentMissionQueue, inbox: OwnerApprovalInbox) -> None:
        self.queue = queue
        self.inbox = inbox

    def check(self) -> tuple[ConsistencyDiagnostic, ...]:
        missions = {mission.mission_id: mission for mission in self.queue.list()}
        approvals = self.inbox.list()
        diagnostics: list[ConsistencyDiagnostic] = []

        for mission in missions.values():
            has_owner = mission.lease_owner is not None
            has_until = mission.lease_until is not None
            if has_owner != has_until:
                diagnostics.append(ConsistencyDiagnostic(
                    "invalid_lease", mission.mission_id,
                    "lease_owner and lease_until must either both be set or both be empty",
                ))
            if mission.status is QueueStatus.RUNNING and not (has_owner and has_until):
                diagnostics.append(ConsistencyDiagnostic(
                    "invalid_running_lease", mission.mission_id,
                    "running mission requires an active lease",
                ))
            if mission.status is not QueueStatus.RUNNING and (has_owner or has_until):
                diagnostics.append(ConsistencyDiagnostic(
                    "terminal_or_idle_state_has_lease", mission.mission_id,
                    f"{mission.status.value} mission must not retain a lease",
                ))

        approvals_by_mission: dict[str, list[object]] = {}
        for approval in approvals:
            approvals_by_mission.setdefault(approval.mission_id, []).append(approval)
            if approval.mission_id not in missions:
                diagnostics.append(ConsistencyDiagnostic(
                    "orphan_approval", approval.mission_id,
                    f"approval {approval.request_id} has no mission queue record",
                ))

        for mission in missions.values():
            waiting = [
                item for item in approvals_by_mission.get(mission.mission_id, [])
                if item.status is ApprovalStatus.WAITING_OWNER_APPROVAL
            ]
            if mission.status is QueueStatus.WAITING_OWNER_APPROVAL and not waiting:
                diagnostics.append(ConsistencyDiagnostic(
                    "waiting_mission_without_approval", mission.mission_id,
                    "mission is waiting for owner approval but no waiting approval exists",
                ))
            if mission.status is not QueueStatus.WAITING_OWNER_APPROVAL and waiting:
                diagnostics.append(ConsistencyDiagnostic(
                    "waiting_approval_state_mismatch", mission.mission_id,
                    "waiting approval exists while mission is not waiting for owner approval",
                ))

        return tuple(sorted(diagnostics))
