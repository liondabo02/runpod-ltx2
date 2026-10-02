from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class VentureState(str, Enum):
    IDEA = "idea"
    VALIDATING = "validating"
    BUILDING = "building"
    OPERATING = "operating"
    PAUSED = "paused"
    RETIRED = "retired"


_ALLOWED_TRANSITIONS: dict[VentureState, frozenset[VentureState]] = {
    VentureState.IDEA: frozenset({VentureState.VALIDATING, VentureState.RETIRED}),
    VentureState.VALIDATING: frozenset(
        {VentureState.BUILDING, VentureState.PAUSED, VentureState.RETIRED}
    ),
    VentureState.BUILDING: frozenset(
        {VentureState.OPERATING, VentureState.PAUSED, VentureState.RETIRED}
    ),
    VentureState.OPERATING: frozenset(
        {VentureState.PAUSED, VentureState.RETIRED}
    ),
    VentureState.PAUSED: frozenset(
        {
            VentureState.VALIDATING,
            VentureState.BUILDING,
            VentureState.OPERATING,
            VentureState.RETIRED,
        }
    ),
    VentureState.RETIRED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Venture:
    venture_id: str
    name: str
    state: VentureState
    opportunity_ids: tuple[str, ...]
    departments: tuple[str, ...]
    objectives: tuple[str, ...]
    budget_ceiling_usd: float
    audit_correlation_id: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not self.venture_id.strip():
            raise ValueError("venture_id must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.budget_ceiling_usd < 0:
            raise ValueError("budget_ceiling_usd must be >= 0")
        if not self.audit_correlation_id.strip():
            raise ValueError("audit_correlation_id must not be empty")


@dataclass(frozen=True, slots=True)
class VentureTransition:
    venture_id: str
    from_state: VentureState
    to_state: VentureState
    timestamp: str
    audit_correlation_id: str


class VentureLifecycle:
    @staticmethod
    def can_transition(from_state: VentureState, to_state: VentureState) -> bool:
        return to_state in _ALLOWED_TRANSITIONS[from_state]

    @staticmethod
    def transition(
        venture: Venture,
        to_state: VentureState,
        *,
        timestamp: str | None = None,
    ) -> tuple[Venture, VentureTransition]:
        if to_state is venture.state:
            raise ValueError("venture is already in the requested state")
        if not VentureLifecycle.can_transition(venture.state, to_state):
            raise ValueError(
                f"invalid venture transition: {venture.state.value} -> {to_state.value}"
            )

        when = timestamp or datetime.now(timezone.utc).isoformat()
        updated = replace(venture, state=to_state, updated_at=when)
        event = VentureTransition(
            venture_id=venture.venture_id,
            from_state=venture.state,
            to_state=to_state,
            timestamp=when,
            audit_correlation_id=venture.audit_correlation_id,
        )
        return updated, event


class VentureRegistry:
    """Persistent local venture registry with deterministic lifecycle rules."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Venture]:
        if not self.path.exists():
            return {}

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("venture registry root must be a JSON object")

        ventures: dict[str, Venture] = {}
        for venture_id, item in raw.items():
            if not isinstance(item, dict):
                raise ValueError(f"venture {venture_id} must be a JSON object")
            ventures[venture_id] = Venture(
                venture_id=item["venture_id"],
                name=item["name"],
                state=VentureState(item["state"]),
                opportunity_ids=tuple(item.get("opportunity_ids", ())),
                departments=tuple(item.get("departments", ())),
                objectives=tuple(item.get("objectives", ())),
                budget_ceiling_usd=float(item.get("budget_ceiling_usd", 0.0)),
                audit_correlation_id=item["audit_correlation_id"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
        return ventures

    def _save(self, ventures: dict[str, Venture]) -> None:
        serializable: dict[str, dict[str, object]] = {}
        for venture_id in sorted(ventures):
            item = ventures[venture_id]
            record = asdict(item)
            record["state"] = item.state.value
            serializable[venture_id] = record

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(
                serializable,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def all(self) -> tuple[Venture, ...]:
        ventures = self._load()
        return tuple(ventures[key] for key in sorted(ventures))

    def get(self, venture_id: str) -> Venture | None:
        return self._load().get(venture_id)

    def create(
        self,
        *,
        venture_id: str,
        name: str,
        opportunity_ids: Iterable[str] = (),
        departments: Iterable[str] = (),
        objectives: Iterable[str] = (),
        budget_ceiling_usd: float = 0.0,
        audit_correlation_id: str | None = None,
        timestamp: str | None = None,
    ) -> Venture:
        ventures = self._load()
        if venture_id in ventures:
            raise ValueError(f"duplicate venture_id: {venture_id}")

        when = timestamp or datetime.now(timezone.utc).isoformat()
        venture = Venture(
            venture_id=venture_id,
            name=name,
            state=VentureState.IDEA,
            opportunity_ids=tuple(dict.fromkeys(opportunity_ids)),
            departments=tuple(dict.fromkeys(departments)),
            objectives=tuple(dict.fromkeys(objectives)),
            budget_ceiling_usd=float(budget_ceiling_usd),
            audit_correlation_id=audit_correlation_id or f"venture:{venture_id}",
            created_at=when,
            updated_at=when,
        )
        ventures[venture_id] = venture
        self._save(ventures)
        return venture

    def transition(
        self,
        venture_id: str,
        to_state: VentureState,
        *,
        timestamp: str | None = None,
    ) -> VentureTransition:
        ventures = self._load()
        venture = ventures.get(venture_id)
        if venture is None:
            raise KeyError(f"unknown venture_id: {venture_id}")

        updated, event = VentureLifecycle.transition(
            venture,
            to_state,
            timestamp=timestamp,
        )
        ventures[venture_id] = updated
        self._save(ventures)
        return event

    def update_links(
        self,
        venture_id: str,
        *,
        opportunity_ids: Iterable[str] | None = None,
        departments: Iterable[str] | None = None,
        objectives: Iterable[str] | None = None,
        budget_ceiling_usd: float | None = None,
        timestamp: str | None = None,
    ) -> Venture:
        ventures = self._load()
        venture = ventures.get(venture_id)
        if venture is None:
            raise KeyError(f"unknown venture_id: {venture_id}")

        when = timestamp or datetime.now(timezone.utc).isoformat()
        updated = replace(
            venture,
            opportunity_ids=(
                tuple(dict.fromkeys(opportunity_ids))
                if opportunity_ids is not None
                else venture.opportunity_ids
            ),
            departments=(
                tuple(dict.fromkeys(departments))
                if departments is not None
                else venture.departments
            ),
            objectives=(
                tuple(dict.fromkeys(objectives))
                if objectives is not None
                else venture.objectives
            ),
            budget_ceiling_usd=(
                float(budget_ceiling_usd)
                if budget_ceiling_usd is not None
                else venture.budget_ceiling_usd
            ),
            updated_at=when,
        )
        if updated.budget_ceiling_usd < 0:
            raise ValueError("budget_ceiling_usd must be >= 0")

        ventures[venture_id] = updated
        self._save(ventures)
        return updated
