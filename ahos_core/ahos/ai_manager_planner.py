from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .mission_orchestrator import MissionStepSpec


PlannerRunner = Callable[[str, Path], Any]


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "mission"


@dataclass(slots=True)
class OpenHandsManagerPlanner:
    """Turn a manager objective into a validated AHOS mission plan.

    The model is never allowed to self-approve protected actions. Any paid,
    external, destructive, or secret-touching step remains owner-gated by AHOS.
    """

    runner: PlannerRunner
    workspace_root: Path
    allowed_departments: frozenset[str]
    max_steps: int = 6
    max_total_estimated_cost_usd: float = 1.0

    def __post_init__(self) -> None:
        self.workspace_root = Path(self.workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.max_total_estimated_cost_usd < 0:
            raise ValueError("max_total_estimated_cost_usd must be >= 0")

    def __call__(
        self,
        mission_id: str,
        objective: str,
        manager_id: str,
    ) -> Iterable[MissionStepSpec]:
        workspace = self.workspace_root / _safe_name(mission_id)
        workspace.mkdir(parents=True, exist_ok=True)
        plan_path = workspace / "MISSION_PLAN.json"
        if plan_path.exists():
            plan_path.unlink()

        prompt = self._prompt(
            mission_id=mission_id,
            objective=objective,
            manager_id=manager_id,
        )
        self.runner(prompt, workspace)

        if not plan_path.exists():
            raise ValueError("manager did not create MISSION_PLAN.json")

        try:
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"manager produced invalid JSON: {exc}") from exc

        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("MISSION_PLAN.json must contain a non-empty steps list")
        if len(raw_steps) > self.max_steps:
            raise ValueError(
                f"manager plan exceeds max_steps={self.max_steps}"
            )

        steps: list[MissionStepSpec] = []
        total_cost = 0.0

        for index, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"step {index} must be a JSON object")

            step_id = str(raw.get("step_id", "")).strip()
            title = str(raw.get("title", "")).strip()
            department = str(raw.get("department", "")).strip().lower()

            if department not in self.allowed_departments:
                raise ValueError(
                    f"step {step_id or index} uses disallowed department "
                    f"{department!r}"
                )

            capabilities_raw = raw.get("required_capabilities", [])
            if not isinstance(capabilities_raw, list):
                raise ValueError(
                    f"step {step_id or index} required_capabilities must be a list"
                )
            capabilities = frozenset(
                str(value).strip()
                for value in capabilities_raw
                if str(value).strip()
            )

            depends_raw = raw.get("depends_on", [])
            if not isinstance(depends_raw, list):
                raise ValueError(
                    f"step {step_id or index} depends_on must be a list"
                )
            depends_on = tuple(
                str(value).strip()
                for value in depends_raw
                if str(value).strip()
            )

            estimated_cost = float(raw.get("estimated_cost_usd", 0.0) or 0.0)
            if estimated_cost < 0:
                raise ValueError("estimated_cost_usd must be >= 0")
            total_cost += estimated_cost

            # A model can request approval-sensitive work, but can never grant
            # itself approval. owner_approved is deliberately forced False.
            steps.append(
                MissionStepSpec(
                    step_id=step_id,
                    title=title,
                    department=department,
                    required_capabilities=capabilities,
                    depends_on=depends_on,
                    estimated_cost_usd=estimated_cost,
                    external_side_effect=bool(
                        raw.get("external_side_effect", False)
                    ),
                    destructive=bool(raw.get("destructive", False)),
                    touches_secrets=bool(raw.get("touches_secrets", False)),
                    requires_owner_approval=bool(
                        raw.get("requires_owner_approval", False)
                    ),
                    owner_approved=False,
                )
            )

        if total_cost > self.max_total_estimated_cost_usd:
            raise ValueError(
                "manager plan exceeds total estimated cost limit: "
                f"{total_cost:.6f} > {self.max_total_estimated_cost_usd:.6f}"
            )

        return tuple(steps)

    def _prompt(
        self,
        *,
        mission_id: str,
        objective: str,
        manager_id: str,
    ) -> str:
        departments = ", ".join(sorted(self.allowed_departments))
        return f"""
You are AHOS department manager {manager_id}.

MISSION ID:
{mission_id}

OBJECTIVE:
{objective}

Create exactly one file named MISSION_PLAN.json in the current workspace.
Do not create or modify any other file.

The file must be valid JSON with this shape:
{{
  "steps": [
    {{
      "step_id": "short-unique-id",
      "title": "clear executable task for one worker",
      "department": "one allowed department",
      "required_capabilities": ["capability"],
      "depends_on": [],
      "estimated_cost_usd": 0.0,
      "external_side_effect": false,
      "destructive": false,
      "touches_secrets": false,
      "requires_owner_approval": false
    }}
  ]
}}

Rules:
- Allowed departments: {departments}
- Maximum {self.max_steps} steps.
- Choose the smallest coherent team and order needed for the objective.
- Express dependencies explicitly in depends_on.
- Keep this plan local-only and reversible.
- Do not plan publishing, messaging, payments, purchases, deployments,
  credential access, destructive actions, or external side effects unless
  the objective explicitly requires them.
- Never claim or set owner approval.
- For this smoke test, all planned worker steps must have
  estimated_cost_usd 0.0 because execution after planning is local.
- Finish only after validating that MISSION_PLAN.json parses as JSON.
""".strip()


def make_builder_planner_runner(builder: Any) -> PlannerRunner:
    def _run(prompt: str, workspace: Path) -> Any:
        return builder.run(task=prompt, workspace=workspace)

    return _run
