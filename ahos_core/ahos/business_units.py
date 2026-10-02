from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class BusinessUnitValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BusinessUnitWorker:
    worker_id: str
    name: str
    role_name: str
    team_id: str
    reports_to: str | None
    capabilities: frozenset[str]
    authority_level: str = "B"
    paid_ai_enabled: bool = False
    external_actions_enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("worker_id", self.worker_id),
            ("name", self.name),
            ("role_name", self.role_name),
            ("team_id", self.team_id),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must not be empty")
        if not self.capabilities:
            raise ValueError("capabilities must not be empty")
        if self.authority_level not in {"A", "B", "C", "D"}:
            raise ValueError("authority_level must be A/B/C/D")


@dataclass(frozen=True, slots=True)
class TeamBlueprint:
    team_id: str
    name: str
    lead_worker_id: str
    mission: str

    def __post_init__(self) -> None:
        for name, value in (
            ("team_id", self.team_id),
            ("name", self.name),
            ("lead_worker_id", self.lead_worker_id),
            ("mission", self.mission),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class BusinessUnitBlueprint:
    business_unit_id: str
    name: str
    director_worker_id: str
    owner_controlled: bool
    teams: tuple[TeamBlueprint, ...]
    workers: tuple[BusinessUnitWorker, ...]
    owner_reserved_decisions: tuple[str, ...]

    def validate(self) -> "BusinessUnitBlueprint":
        errors: list[str] = []

        if not self.business_unit_id.strip():
            errors.append("business_unit_id must not be empty")
        if not self.name.strip():
            errors.append("name must not be empty")
        if not self.owner_controlled:
            errors.append("business unit must remain owner controlled")

        worker_ids = [w.worker_id for w in self.workers]
        if len(worker_ids) != len(set(worker_ids)):
            errors.append("duplicate worker_id detected")

        team_ids = [t.team_id for t in self.teams]
        if len(team_ids) != len(set(team_ids)):
            errors.append("duplicate team_id detected")

        workers = {w.worker_id: w for w in self.workers}
        teams = {t.team_id: t for t in self.teams}

        if self.director_worker_id not in workers:
            errors.append("director_worker_id does not exist")
        else:
            director = workers[self.director_worker_id]
            if director.reports_to is not None:
                errors.append("business unit director must report directly to owner")

        for team in self.teams:
            lead = workers.get(team.lead_worker_id)
            if lead is None:
                errors.append(f"team {team.team_id} lead does not exist")
            elif lead.team_id != team.team_id:
                errors.append(
                    f"team {team.team_id} lead belongs to {lead.team_id}"
                )

        for worker in self.workers:
            if worker.team_id not in teams:
                errors.append(
                    f"worker {worker.worker_id} references unknown team {worker.team_id}"
                )
            if worker.worker_id != self.director_worker_id:
                if worker.reports_to is None:
                    errors.append(
                        f"worker {worker.worker_id} must report to another studio worker"
                    )
                elif worker.reports_to not in workers:
                    errors.append(
                        f"worker {worker.worker_id} reports to unknown worker "
                        f"{worker.reports_to}"
                    )

        # Detect reporting cycles and require every worker to eventually reach
        # the studio director.
        for worker in self.workers:
            if worker.worker_id == self.director_worker_id:
                continue
            seen: set[str] = set()
            current = worker
            while current.worker_id != self.director_worker_id:
                if current.worker_id in seen:
                    errors.append(
                        f"reporting cycle detected at {current.worker_id}"
                    )
                    break
                seen.add(current.worker_id)
                if current.reports_to is None:
                    errors.append(
                        f"worker {worker.worker_id} does not reach studio director"
                    )
                    break
                parent = workers.get(current.reports_to)
                if parent is None:
                    break
                current = parent

        if not self.owner_reserved_decisions:
            errors.append("owner_reserved_decisions must not be empty")

        if errors:
            raise BusinessUnitValidationError("; ".join(sorted(set(errors))))
        return self

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "business_unit_id": self.business_unit_id,
            "name": self.name,
            "director_worker_id": self.director_worker_id,
            "owner_controlled": self.owner_controlled,
            "owner_reserved_decisions": list(self.owner_reserved_decisions),
            "teams": [
                {
                    "team_id": t.team_id,
                    "name": t.name,
                    "lead_worker_id": t.lead_worker_id,
                    "mission": t.mission,
                }
                for t in self.teams
            ],
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "name": w.name,
                    "role_name": w.role_name,
                    "team_id": w.team_id,
                    "reports_to": w.reports_to,
                    "capabilities": sorted(w.capabilities),
                    "authority_level": w.authority_level,
                    "paid_ai_enabled": w.paid_ai_enabled,
                    "external_actions_enabled": w.external_actions_enabled,
                }
                for w in self.workers
            ],
        }
