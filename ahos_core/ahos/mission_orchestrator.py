from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable, Mapping, Protocol

from .virtual_workforce import VirtualWorkforceRegistry
from .worker_runtime import (
    QaExecutor,
    VirtualWorkerRuntime,
    WorkerExecutionResult,
    WorkerExecutor,
)
from .workforce_execution import WorkItem, WorkStage, manager_for_department


class OwnerApprovalPending(RuntimeError):
    """Protected work is waiting for explicit owner approval."""


class OwnerApprovalRejected(RuntimeError):
    """The owner explicitly rejected protected work."""


class MissionStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    WAITING_OWNER_APPROVAL = "waiting_owner_approval"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class MissionStepSpec:
    step_id: str
    title: str
    department: str
    required_capabilities: frozenset[str]
    depends_on: tuple[str, ...] = ()
    estimated_cost_usd: float = 0.0
    external_side_effect: bool = False
    destructive: bool = False
    touches_secrets: bool = False
    requires_owner_approval: bool = False
    owner_approved: bool = False

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.department.strip():
            raise ValueError("department must not be empty")
        if self.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be >= 0")


@dataclass(frozen=True, slots=True)
class MissionPlan:
    mission_id: str
    objective: str
    manager_id: str
    steps: tuple[MissionStepSpec, ...]


@dataclass(frozen=True, slots=True)
class MissionStepResult:
    step: MissionStepSpec
    stage: WorkStage
    worker_id: str | None
    worker_summary: str | None
    qa_summary: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class MissionResult:
    mission_id: str
    objective: str
    manager_id: str | None
    status: MissionStatus
    steps: tuple[MissionStepResult, ...]
    reason: str


class ManagerPlanner(Protocol):
    def __call__(
        self,
        mission_id: str,
        objective: str,
        manager_id: str,
    ) -> Iterable[MissionStepSpec]: ...


class DepartmentManager:
    """Leases a real AHOS manager worker and asks an injected planner for a plan."""

    def __init__(
        self,
        registry: VirtualWorkforceRegistry,
        planner: ManagerPlanner,
    ) -> None:
        self.registry = registry
        self.planner = planner

    def create_plan(
        self,
        *,
        mission_id: str,
        objective: str,
        primary_department: str,
    ) -> MissionPlan:
        manager = manager_for_department(self.registry.all(), primary_department)
        if manager is None:
            raise RuntimeError(
                f"no department manager available for {primary_department}"
            )

        lease_id = f"{mission_id}:planning"
        self.registry.assign(manager.profile.worker_id, lease_id)
        try:
            steps = tuple(
                self.planner(
                    mission_id,
                    objective,
                    manager.profile.worker_id,
                )
            )
        finally:
            self.registry.release(manager.profile.worker_id, lease_id)

        self._validate_steps(steps)

        return MissionPlan(
            mission_id=mission_id,
            objective=objective,
            manager_id=manager.profile.worker_id,
            steps=steps,
        )

    @staticmethod
    def _validate_steps(steps: tuple[MissionStepSpec, ...]) -> None:
        if not steps:
            raise ValueError("mission plan must contain at least one step")

        ids = [step.step_id for step in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("mission plan contains duplicate step_id values")

        known = set(ids)
        for step in steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(
                    f"step {step.step_id} depends on unknown steps: {sorted(missing)}"
                )
            if step.step_id in step.depends_on:
                raise ValueError(f"step {step.step_id} cannot depend on itself")

        # Detect cycles with a small deterministic topological pass.
        remaining = {step.step_id: set(step.depends_on) for step in steps}
        completed: set[str] = set()

        while remaining:
            ready = sorted(
                step_id
                for step_id, deps in remaining.items()
                if deps.issubset(completed)
            )
            if not ready:
                raise ValueError("mission plan contains a dependency cycle")
            for step_id in ready:
                completed.add(step_id)
                remaining.pop(step_id)


class MultiWorkerMissionOrchestrator:
    """Runs a manager-created mission across multiple AHOS virtual workers.

    Planning and worker execution are injected. This module itself performs no
    network or LLM call. Each work step still passes through the existing
    worker -> QA lifecycle and all approval/budget gates.
    """

    def __init__(
        self,
        registry: VirtualWorkforceRegistry,
        *,
        manager_planner: ManagerPlanner,
        executors: Mapping[str, WorkerExecutor],
        qa_executor: QaExecutor,
    ) -> None:
        self.registry = registry
        self.manager = DepartmentManager(registry, manager_planner)
        self.runtime = VirtualWorkerRuntime(
            registry=registry,
            executors=executors,
            qa_executor=qa_executor,
        )

    def run(
        self,
        *,
        mission_id: str,
        objective: str,
        primary_department: str,
    ) -> MissionResult:
        try:
            plan = self.manager.create_plan(
                mission_id=mission_id,
                objective=objective,
                primary_department=primary_department,
            )
        except OwnerApprovalPending as exc:
            return MissionResult(
                mission_id=mission_id,
                objective=objective,
                manager_id=None,
                status=MissionStatus.WAITING_OWNER_APPROVAL,
                steps=(),
                reason=str(exc),
            )
        except (OwnerApprovalRejected, RuntimeError, ValueError) as exc:
            return MissionResult(
                mission_id=mission_id,
                objective=objective,
                manager_id=None,
                status=MissionStatus.BLOCKED,
                steps=(),
                reason=str(exc),
            )

        pending = {step.step_id: step for step in plan.steps}
        completed: dict[str, MissionStepResult] = {}
        ordered_results: list[MissionStepResult] = []

        while pending:
            ready = [
                step
                for step in plan.steps
                if step.step_id in pending
                and all(dep in completed for dep in step.depends_on)
            ]

            if not ready:
                return MissionResult(
                    mission_id=mission_id,
                    objective=objective,
                    manager_id=plan.manager_id,
                    status=MissionStatus.BLOCKED,
                    steps=tuple(ordered_results),
                    reason="mission execution stalled on unresolved dependencies",
                )

            for step in ready:
                work_item = self._to_work_item(
                    plan=plan,
                    step=step,
                    completed=completed,
                )
                run = self.runtime.run(work_item)

                result = MissionStepResult(
                    step=step,
                    stage=run.stage,
                    worker_id=run.assignment.worker_id,
                    worker_summary=(
                        run.worker_result.summary if run.worker_result else None
                    ),
                    qa_summary=(
                        run.qa_result.summary if run.qa_result else None
                    ),
                    reason=run.reason,
                )

                ordered_results.append(result)
                pending.pop(step.step_id)

                if run.stage is not WorkStage.COMPLETED:
                    return MissionResult(
                        mission_id=mission_id,
                        objective=objective,
                        manager_id=plan.manager_id,
                        status=MissionStatus.BLOCKED,
                        steps=tuple(ordered_results),
                        reason=(
                            f"mission blocked at step {step.step_id}: "
                            f"{run.reason}"
                        ),
                    )

                completed[step.step_id] = result

        return MissionResult(
            mission_id=mission_id,
            objective=objective,
            manager_id=plan.manager_id,
            status=MissionStatus.COMPLETED,
            steps=tuple(ordered_results),
            reason="all mission steps completed and passed QA",
        )

    @staticmethod
    def _to_work_item(
        *,
        plan: MissionPlan,
        step: MissionStepSpec,
        completed: Mapping[str, MissionStepResult],
    ) -> WorkItem:
        dependency_context: list[str] = []

        for dep_id in step.depends_on:
            dep = completed[dep_id]
            if dep.worker_summary:
                dependency_context.append(
                    f"{dep_id}: {dep.worker_summary}"
                )

        context = ""
        if dependency_context:
            context = (
                "\n\nPrevious completed step results:\n- "
                + "\n- ".join(dependency_context)
            )

        title = (
            f"Mission objective: {plan.objective}\n"
            f"Current step: {step.title}"
            f"{context}"
        )

        return WorkItem(
            task_id=f"{plan.mission_id}:{step.step_id}",
            title=title,
            department=step.department,
            required_capabilities=step.required_capabilities,
            estimated_cost_usd=step.estimated_cost_usd,
            external_side_effect=step.external_side_effect,
            destructive=step.destructive,
            touches_secrets=step.touches_secrets,
            requires_owner_approval=step.requires_owner_approval,
            owner_approved=step.owner_approved,
        )
