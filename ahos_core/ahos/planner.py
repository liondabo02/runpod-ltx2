from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


class MissionPlanningError(ValueError):
    """Base error for invalid mission graphs."""


class UnknownDependencyError(MissionPlanningError):
    """Raised when a mission depends on a mission not in the graph."""

    def __init__(self, mission_id: str, dependency_id: str) -> None:
        self.mission_id = mission_id
        self.dependency_id = dependency_id
        super().__init__(
            f"mission {mission_id!r} depends on unknown mission {dependency_id!r}"
        )


class DependencyCycleError(MissionPlanningError):
    """Raised when mission dependencies contain a cycle."""

    def __init__(self, cycle: Iterable[str]) -> None:
        self.cycle = tuple(cycle)
        super().__init__(f"mission dependency cycle detected: {' -> '.join(self.cycle)}")


@dataclass(frozen=True, slots=True)
class MissionDefinition:
    """Local, side-effect-free description of a mission to be planned."""

    mission_id: str
    priority: int = 0
    dependencies: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.mission_id:
            raise ValueError("mission_id must not be empty")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise TypeError("priority must be an integer")
        object.__setattr__(self, "dependencies", frozenset(self.dependencies))


class MissionPlanner:
    """Deterministically order local missions while respecting dependencies."""

    def __init__(self, missions: Iterable[MissionDefinition] = ()) -> None:
        self._missions: dict[str, MissionDefinition] = {}
        for mission in missions:
            if mission.mission_id in self._missions:
                raise ValueError(f"mission {mission.mission_id!r} already exists")
            self._missions[mission.mission_id] = mission
        self._validate_graph()

    def add_mission(self, mission: MissionDefinition) -> None:
        if mission.mission_id in self._missions:
            raise ValueError(f"mission {mission.mission_id!r} already exists")
        self._missions[mission.mission_id] = mission
        try:
            self._validate_cycles()
        except Exception:
            del self._missions[mission.mission_id]
            raise

    def get_mission(self, mission_id: str) -> MissionDefinition | None:
        return self._missions.get(mission_id)

    def ready_missions(self, completed_ids: Iterable[str] = ()) -> list[MissionDefinition]:
        """Return pending missions whose dependencies are already completed."""

        self._validate_graph()
        completed = frozenset(completed_ids)
        return sorted(
            (
                mission
                for mission in self._missions.values()
                if mission.mission_id not in completed
                and mission.dependencies <= completed
            ),
            key=_priority_key,
        )

    def is_ready(self, mission_id: str, completed_ids: Iterable[str] = ()) -> bool:
        self._validate_graph()
        mission = self._require_mission(mission_id)
        completed = frozenset(completed_ids)
        return mission_id not in completed and mission.dependencies <= completed

    def plan(self, completed_ids: Iterable[str] = ()) -> list[str]:
        """Return a deterministic dependency-safe order for pending missions.

        Higher priority missions are selected first whenever they are both ready;
        mission ID breaks priority ties. Completed missions satisfy dependencies
        and are omitted from the returned order.
        """

        self._validate_graph()
        completed = frozenset(completed_ids)
        pending = set(self._missions) - completed
        remaining_dependencies = {
            mission_id: {
                dependency
                for dependency in mission.dependencies
                if dependency in pending
            }
            for mission_id, mission in self._missions.items()
            if mission_id in pending
        }
        ordered: list[str] = []

        while pending:
            available = sorted(
                (
                    self._missions[mission_id]
                    for mission_id in pending
                    if not remaining_dependencies[mission_id]
                ),
                key=_priority_key,
            )
            if not available:
                raise DependencyCycleError(self._find_cycle())
            mission = available[0]
            pending.remove(mission.mission_id)
            ordered.append(mission.mission_id)
            for dependencies in remaining_dependencies.values():
                dependencies.discard(mission.mission_id)

        return ordered

    def _require_mission(self, mission_id: str) -> MissionDefinition:
        try:
            return self._missions[mission_id]
        except KeyError:
            raise KeyError(f"unknown mission {mission_id!r}") from None

    def _validate_graph(self) -> None:
        for mission in self._missions.values():
            for dependency in sorted(mission.dependencies):
                if dependency not in self._missions:
                    raise UnknownDependencyError(mission.mission_id, dependency)
        self._validate_cycles()

    def _validate_cycles(self) -> None:
        cycle = self._find_cycle()
        if cycle:
            raise DependencyCycleError(cycle)

    def _find_cycle(self) -> tuple[str, ...]:
        visited: set[str] = set()
        active: list[str] = []
        active_positions: dict[str, int] = {}

        def visit(mission_id: str) -> tuple[str, ...] | None:
            if mission_id in active_positions:
                return tuple(active[active_positions[mission_id] :] + [mission_id])
            if mission_id in visited:
                return None

            visited.add(mission_id)
            active_positions[mission_id] = len(active)
            active.append(mission_id)
            mission = self._missions[mission_id]
            for dependency in sorted(mission.dependencies):
                if dependency in self._missions:
                    cycle = visit(dependency)
                    if cycle:
                        return cycle
            active.pop()
            del active_positions[mission_id]
            return None

        for mission_id in sorted(self._missions):
            cycle = visit(mission_id)
            if cycle:
                return cycle
        return ()


def _priority_key(mission: MissionDefinition) -> tuple[int, str]:
    return (-mission.priority, mission.mission_id)
