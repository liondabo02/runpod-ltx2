from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .virtual_workforce import WorkerProfile, WorkerRole


CORE_DEPARTMENTS: tuple[str, ...] = (
    "software",
    "quality",
    "research",
    "infrastructure",
    "data",
    "creative",
    "marketing",
    "sales",
    "finance",
    "operations",
    "support",
)


@dataclass(frozen=True, slots=True)
class DepartmentStructure:
    department: str
    manager_id: str
    worker_ids: tuple[str, ...]


def build_department_structure(
    workers: Iterable[WorkerProfile],
) -> tuple[DepartmentStructure, ...]:
    profiles = tuple(workers)
    result: list[DepartmentStructure] = []

    for department in CORE_DEPARTMENTS:
        members = tuple(
            sorted(
                (
                    profile
                    for profile in profiles
                    if profile.department == department
                ),
                key=lambda profile: profile.worker_id,
            )
        )
        managers = tuple(
            profile
            for profile in members
            if profile.role is WorkerRole.DEPARTMENT_MANAGER
        )
        specialists = tuple(
            profile
            for profile in members
            if profile.role is not WorkerRole.DEPARTMENT_MANAGER
        )

        if len(managers) != 1:
            raise ValueError(
                f"department {department} must have exactly one manager; "
                f"found {len(managers)}"
            )
        if not specialists:
            raise ValueError(
                f"department {department} must have at least one specialist"
            )

        result.append(
            DepartmentStructure(
                department=department,
                manager_id=managers[0].worker_id,
                worker_ids=tuple(profile.worker_id for profile in specialists),
            )
        )

    return tuple(result)
