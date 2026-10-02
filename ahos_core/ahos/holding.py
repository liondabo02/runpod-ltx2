from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .audit import AuditLog
from .finance import FinancialLedger, UnitEconomicsSnapshot
from .governance import AuthorityLevel
from .opportunity import Opportunity, OpportunityScore, OpportunityScorer, OpportunityStore
from .routing import DepartmentRoutingEngine
from .venture import Venture, VentureRegistry
from .work_order import WorkOrder, WorkOrderStore


@dataclass(frozen=True, slots=True)
class HoldingPaths:
    root: Path

    @property
    def opportunities(self) -> Path:
        return self.root / "opportunities.jsonl"

    @property
    def ventures(self) -> Path:
        return self.root / "ventures.json"

    @property
    def work_orders(self) -> Path:
        return self.root / "work_orders.json"

    @property
    def ledger(self) -> Path:
        return self.root / "ledger.jsonl"

    @property
    def audit(self) -> Path:
        return self.root / "holding_audit.jsonl"


@dataclass(frozen=True, slots=True)
class OpportunityDecision:
    opportunity: Opportunity
    score: OpportunityScore
    qualified: bool
    threshold: float


class HoldingOperatingEngine:
    """Local-only coordinator that connects the AHOS holding primitives.

    This layer deliberately performs no network calls, outreach, purchases,
    publishing, payments, or other external side effects.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        qualification_threshold: float = 60.0,
    ) -> None:
        if not 0 <= qualification_threshold <= 100:
            raise ValueError("qualification_threshold must be between 0 and 100")

        self.paths = HoldingPaths(Path(root))
        self.paths.root.mkdir(parents=True, exist_ok=True)

        self.opportunities = OpportunityStore(self.paths.opportunities)
        self.ventures = VentureRegistry(self.paths.ventures)
        self.work_orders = WorkOrderStore(self.paths.work_orders)
        self.ledger = FinancialLedger(self.paths.ledger)
        self.audit = AuditLog(self.paths.audit)
        self.scorer = OpportunityScorer()
        self.router = DepartmentRoutingEngine()
        self.qualification_threshold = float(qualification_threshold)

    def evaluate_opportunity(
        self,
        opportunity: Opportunity,
        *,
        timestamp: str | None = None,
    ) -> OpportunityDecision:
        stored = self.opportunities.append(opportunity, timestamp=timestamp)
        score = self.scorer.score(stored)
        qualified = score.score >= self.qualification_threshold

        self.audit.append(
            "opportunity_evaluated",
            {
                "opportunity_id": stored.opportunity_id,
                "score": score.score,
                "qualified": qualified,
                "threshold": self.qualification_threshold,
            },
            correlation_id=f"opportunity:{stored.opportunity_id}",
            timestamp=timestamp,
        )

        return OpportunityDecision(
            opportunity=stored,
            score=score,
            qualified=qualified,
            threshold=self.qualification_threshold,
        )

    def create_venture(
        self,
        *,
        venture_id: str,
        name: str,
        opportunity_id: str,
        objectives: tuple[str, ...] = (),
        budget_ceiling_usd: float = 0.0,
        timestamp: str | None = None,
    ) -> Venture:
        if self.opportunities.get(opportunity_id) is None:
            raise KeyError(f"unknown opportunity_id: {opportunity_id}")

        venture = self.ventures.create(
            venture_id=venture_id,
            name=name,
            opportunity_ids=(opportunity_id,),
            objectives=objectives,
            budget_ceiling_usd=budget_ceiling_usd,
            audit_correlation_id=f"venture:{venture_id}",
            timestamp=timestamp,
        )

        self.audit.append(
            "venture_created",
            {
                "venture_id": venture_id,
                "opportunity_id": opportunity_id,
                "budget_ceiling_usd": budget_ceiling_usd,
            },
            correlation_id=venture.audit_correlation_id,
            timestamp=timestamp,
        )

        return venture

    def create_work_order(
        self,
        *,
        work_order_id: str,
        venture_id: str,
        mission_id: str,
        objective: str,
        required_capabilities: tuple[str, ...] = (),
        priority: int = 0,
        dependencies: tuple[str, ...] = (),
        budget_ceiling_usd: float = 0.0,
        max_authority: AuthorityLevel = AuthorityLevel.B,
        timestamp: str | None = None,
    ) -> WorkOrder:
        venture = self.ventures.get(venture_id)
        if venture is None:
            raise KeyError(f"unknown venture_id: {venture_id}")

        route = self.router.route_mission(
            mission_id,
            objective,
            required_capabilities=required_capabilities,
            max_authority=max_authority,
        )

        routing_department = (
            route.primary.department.value
            if route.primary is not None
            else None
        )
        routing_score = (
            float(route.primary.score)
            if route.primary is not None
            else None
        )

        order = self.work_orders.create(
            work_order_id=work_order_id,
            venture_id=venture_id,
            mission_id=mission_id,
            capability_requirements=required_capabilities,
            priority=priority,
            dependencies=dependencies,
            budget_ceiling_usd=budget_ceiling_usd,
            routing_department=routing_department,
            routing_score=routing_score,
            audit_correlation_id=f"work-order:{work_order_id}",
            timestamp=timestamp,
        )

        self.audit.append(
            "work_order_created",
            {
                "work_order_id": work_order_id,
                "venture_id": venture_id,
                "mission_id": mission_id,
                "routing_department": routing_department,
                "routing_score": routing_score,
                "blocked_capabilities": list(route.blocked_capabilities),
                "unmatched_required_capabilities": list(
                    route.unmatched_required_capabilities
                ),
            },
            correlation_id=order.audit_correlation_id,
            timestamp=timestamp,
        )

        return order

    def venture_snapshot(self, venture_id: str) -> UnitEconomicsSnapshot:
        if self.ventures.get(venture_id) is None:
            raise KeyError(f"unknown venture_id: {venture_id}")
        return self.ledger.snapshot(venture_id)
