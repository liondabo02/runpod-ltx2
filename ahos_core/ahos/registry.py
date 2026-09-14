from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentLease:
    agent_id: str
    mission_id: str


class AgentRegistry:
    """Prevents the same logical agent from running two missions at once."""

    def __init__(self) -> None:
        self._leases: dict[str, AgentLease] = {}

    def acquire(self, agent_id: str, mission_id: str) -> AgentLease:
        if agent_id in self._leases:
            current = self._leases[agent_id]
            raise RuntimeError(
                f"agent {agent_id!r} already assigned to mission {current.mission_id!r}"
            )
        lease = AgentLease(agent_id=agent_id, mission_id=mission_id)
        self._leases[agent_id] = lease
        return lease

    def release(self, agent_id: str, mission_id: str) -> None:
        current = self._leases.get(agent_id)
        if current is None:
            return
        if current.mission_id != mission_id:
            raise RuntimeError("cannot release an agent lease owned by another mission")
        del self._leases[agent_id]

    def is_busy(self, agent_id: str) -> bool:
        return agent_id in self._leases
