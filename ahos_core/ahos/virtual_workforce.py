from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class WorkerStatus(str, Enum):
    IDLE = "idle"
    ASSIGNED = "assigned"
    PAUSED = "paused"
    DISABLED = "disabled"


class WorkerRole(str, Enum):
    DEPARTMENT_MANAGER = "department_manager"
    SOFTWARE_ENGINEER = "software_engineer"
    RESEARCHER = "researcher"
    QA_ENGINEER = "qa_engineer"
    DEVOPS_ENGINEER = "devops_engineer"
    DATA_ANALYST = "data_analyst"
    DESIGNER = "designer"
    MARKETING_SPECIALIST = "marketing_specialist"
    SALES_SPECIALIST = "sales_specialist"
    FINANCE_SPECIALIST = "finance_specialist"
    OPERATIONS_SPECIALIST = "operations_specialist"
    CUSTOMER_SUPPORT = "customer_support"


@dataclass(frozen=True, slots=True)
class WorkerProfile:
    worker_id: str
    name: str
    role: WorkerRole
    department: str
    capabilities: frozenset[str]
    authority_level: str = "B"
    max_parallel_tasks: int = 1
    daily_budget_usd: float = 0.0
    can_use_paid_ai: bool = False

    def __post_init__(self) -> None:
        if not self.worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.department.strip():
            raise ValueError("department must not be empty")
        if self.max_parallel_tasks < 1:
            raise ValueError("max_parallel_tasks must be >= 1")
        if self.daily_budget_usd < 0:
            raise ValueError("daily_budget_usd must be >= 0")


@dataclass(slots=True)
class WorkerRuntimeState:
    profile: WorkerProfile
    status: WorkerStatus = WorkerStatus.IDLE
    active_task_ids: set[str] = field(default_factory=set)
    spend_today_usd: float = 0.0

    @property
    def available_slots(self) -> int:
        if self.status in {WorkerStatus.PAUSED, WorkerStatus.DISABLED}:
            return 0
        return max(0, self.profile.max_parallel_tasks - len(self.active_task_ids))

    @property
    def is_available(self) -> bool:
        return self.available_slots > 0

    def can_afford(self, estimated_cost_usd: float) -> bool:
        if estimated_cost_usd <= 0:
            return True
        if not self.profile.can_use_paid_ai:
            return False
        return (self.spend_today_usd + estimated_cost_usd) <= self.profile.daily_budget_usd


class VirtualWorkforceRegistry:
    """In-memory registry for AHOS virtual workers.

    It handles worker identity, capabilities, task leases and budget gates.
    External actions and AI calls are deliberately outside this class.
    """

    def __init__(self, workers: Iterable[WorkerProfile] = ()) -> None:
        self._workers: dict[str, WorkerRuntimeState] = {}
        for worker in workers:
            self.register(worker)

    def register(self, profile: WorkerProfile) -> WorkerRuntimeState:
        if profile.worker_id in self._workers:
            raise ValueError(f"duplicate worker_id: {profile.worker_id}")
        state = WorkerRuntimeState(profile=profile)
        self._workers[profile.worker_id] = state
        return state

    def get(self, worker_id: str) -> WorkerRuntimeState:
        try:
            return self._workers[worker_id]
        except KeyError as exc:
            raise KeyError(f"unknown worker_id: {worker_id}") from exc

    def all(self) -> tuple[WorkerRuntimeState, ...]:
        return tuple(self._workers[key] for key in sorted(self._workers))

    def matching_workers(
        self,
        required_capabilities: Iterable[str],
        *,
        department: str | None = None,
        estimated_cost_usd: float = 0.0,
    ) -> tuple[WorkerRuntimeState, ...]:
        required = frozenset(required_capabilities)
        matches: list[WorkerRuntimeState] = []

        for state in self._workers.values():
            if department and state.profile.department != department:
                continue
            if not state.is_available:
                continue
            if not required.issubset(state.profile.capabilities):
                continue
            if not state.can_afford(estimated_cost_usd):
                continue
            matches.append(state)

        matches.sort(
            key=lambda state: (
                -state.available_slots,
                state.spend_today_usd,
                state.profile.worker_id,
            )
        )
        return tuple(matches)

    def assign(
        self,
        worker_id: str,
        task_id: str,
        *,
        estimated_cost_usd: float = 0.0,
    ) -> WorkerRuntimeState:
        state = self.get(worker_id)
        if task_id in state.active_task_ids:
            return state
        if not state.is_available:
            raise RuntimeError(f"worker {worker_id} has no available task slot")
        if not state.can_afford(estimated_cost_usd):
            raise RuntimeError(f"worker {worker_id} budget gate denied assignment")

        state.active_task_ids.add(task_id)
        state.status = WorkerStatus.ASSIGNED
        return state

    def release(self, worker_id: str, task_id: str) -> WorkerRuntimeState:
        state = self.get(worker_id)
        state.active_task_ids.discard(task_id)
        if not state.active_task_ids and state.status is WorkerStatus.ASSIGNED:
            state.status = WorkerStatus.IDLE
        return state

    def record_spend(self, worker_id: str, amount_usd: float) -> WorkerRuntimeState:
        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        state = self.get(worker_id)
        new_total = state.spend_today_usd + amount_usd
        if new_total > state.profile.daily_budget_usd:
            raise RuntimeError(f"worker {worker_id} daily budget exceeded")
        state.spend_today_usd = new_total
        return state

    def pause(self, worker_id: str) -> WorkerRuntimeState:
        state = self.get(worker_id)
        state.status = WorkerStatus.PAUSED
        return state

    def resume(self, worker_id: str) -> WorkerRuntimeState:
        state = self.get(worker_id)
        state.status = (
            WorkerStatus.ASSIGNED if state.active_task_ids else WorkerStatus.IDLE
        )
        return state


def default_virtual_workforce() -> tuple[WorkerProfile, ...]:
    """Initial AHOS virtual employee roster.

    Paid AI is disabled by default for every worker. Budgets can be enabled
    explicitly later at worker/department level.
    """
    return (
        WorkerProfile(
            worker_id="mgr-software-01",
            name="Software Department Manager",
            role=WorkerRole.DEPARTMENT_MANAGER,
            department="software",
            capabilities=frozenset(
                {"planning", "task_decomposition", "routing", "code_review"}
            ),
        ),
        WorkerProfile(
            worker_id="dev-01",
            name="Software Engineer 01",
            role=WorkerRole.SOFTWARE_ENGINEER,
            department="software",
            capabilities=frozenset(
                {"python", "backend", "api", "automation", "testing", "git"}
            ),
        ),
        WorkerProfile(
            worker_id="qa-01",
            name="QA Engineer 01",
            role=WorkerRole.QA_ENGINEER,
            department="quality",
            capabilities=frozenset(
                {"testing", "qa", "verification", "regression", "code_review"}
            ),
        ),
        WorkerProfile(
            worker_id="research-01",
            name="Researcher 01",
            role=WorkerRole.RESEARCHER,
            department="research",
            capabilities=frozenset(
                {"research", "analysis", "summarization", "source_review"}
            ),
        ),
        WorkerProfile(
            worker_id="devops-01",
            name="DevOps Engineer 01",
            role=WorkerRole.DEVOPS_ENGINEER,
            department="infrastructure",
            capabilities=frozenset(
                {"devops", "ci", "deployment", "monitoring", "git"}
            ),
        ),
        WorkerProfile(
            worker_id="data-01",
            name="Data Analyst 01",
            role=WorkerRole.DATA_ANALYST,
            department="data",
            capabilities=frozenset(
                {"data", "analytics", "python", "reporting"}
            ),
        ),
        WorkerProfile(
            worker_id="design-01",
            name="Designer 01",
            role=WorkerRole.DESIGNER,
            department="creative",
            capabilities=frozenset(
                {"design", "creative", "content", "visual_review"}
            ),
        ),
        WorkerProfile(
            worker_id="marketing-01",
            name="Marketing Specialist 01",
            role=WorkerRole.MARKETING_SPECIALIST,
            department="marketing",
            capabilities=frozenset(
                {"marketing", "content", "seo", "campaign_planning"}
            ),
        ),
        WorkerProfile(
            worker_id="sales-01",
            name="Sales Specialist 01",
            role=WorkerRole.SALES_SPECIALIST,
            department="sales",
            capabilities=frozenset(
                {"sales", "lead_research", "proposal_drafting", "crm"}
            ),
        ),
        WorkerProfile(
            worker_id="finance-01",
            name="Finance Specialist 01",
            role=WorkerRole.FINANCE_SPECIALIST,
            department="finance",
            capabilities=frozenset(
                {"finance", "cost_tracking", "budgeting", "reporting"}
            ),
        ),
        WorkerProfile(
            worker_id="ops-01",
            name="Operations Specialist 01",
            role=WorkerRole.OPERATIONS_SPECIALIST,
            department="operations",
            capabilities=frozenset(
                {"operations", "scheduling", "coordination", "workflow"}
            ),
        ),
        WorkerProfile(
            worker_id="support-01",
            name="Customer Support 01",
            role=WorkerRole.CUSTOMER_SUPPORT,
            department="support",
            capabilities=frozenset(
                {"support", "ticket_triage", "knowledge_base", "drafting"}
            ),
        ),
    )
