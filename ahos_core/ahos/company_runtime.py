from __future__ import annotations

from dataclasses import dataclass

from .autonomous_company import QueuedMission
from .mission_orchestrator import MissionResult, MultiWorkerMissionOrchestrator


@dataclass(slots=True)
class OrchestratedMissionExecutor:
    """Adapter that turns one queued company mission into an AHOS mission run.

    Queue persistence/retry/lease behavior remains in autonomous_company.
    Planning, routing, workers, QA, and approval gates remain in the existing
    MultiWorkerMissionOrchestrator stack.
    """

    orchestrator: MultiWorkerMissionOrchestrator

    def __call__(self, mission: QueuedMission) -> MissionResult:
        return self.orchestrator.run(
            mission_id=mission.mission_id,
            objective=mission.objective,
            primary_department=mission.primary_department,
        )
