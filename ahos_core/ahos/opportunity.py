from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class OpportunityStatus(str, Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Opportunity:
    opportunity_id: str
    title: str
    source: str
    category: str
    expected_value_usd: float
    effort: float
    risk: float
    confidence: float
    strategic_fit: float
    status: OpportunityStatus = OpportunityStatus.NEW
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.opportunity_id.strip():
            raise ValueError("opportunity_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not self.category.strip():
            raise ValueError("category must not be empty")
        if self.expected_value_usd < 0:
            raise ValueError("expected_value_usd must be >= 0")
        for name in ("effort", "risk", "confidence", "strategic_fit"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    def with_timestamp(self, timestamp: str | None = None) -> "Opportunity":
        if self.created_at:
            return self
        return Opportunity(
            opportunity_id=self.opportunity_id,
            title=self.title,
            source=self.source,
            category=self.category,
            expected_value_usd=self.expected_value_usd,
            effort=self.effort,
            risk=self.risk,
            confidence=self.confidence,
            strategic_fit=self.strategic_fit,
            status=self.status,
            created_at=timestamp or datetime.now(timezone.utc).isoformat(),
        )


@dataclass(frozen=True, slots=True)
class OpportunityScore:
    opportunity_id: str
    score: float
    value_component: float
    effort_component: float
    risk_component: float
    confidence_component: float
    strategic_fit_component: float


class OpportunityScorer:
    """Deterministic, local-only opportunity scoring.

    Score is out of 100:
      expected value   35
      low effort       20
      low risk         15
      confidence       15
      strategic fit    15

    expected_value_reference_usd is the value that receives the full 35 points.
    Values above it are capped, making the result stable and bounded.
    """

    def __init__(self, expected_value_reference_usd: float = 10_000.0) -> None:
        if expected_value_reference_usd <= 0:
            raise ValueError("expected_value_reference_usd must be > 0")
        self.expected_value_reference_usd = float(expected_value_reference_usd)

    def score(self, opportunity: Opportunity) -> OpportunityScore:
        value_ratio = min(
            opportunity.expected_value_usd / self.expected_value_reference_usd,
            1.0,
        )
        value_component = value_ratio * 35.0
        effort_component = (1.0 - opportunity.effort) * 20.0
        risk_component = (1.0 - opportunity.risk) * 15.0
        confidence_component = opportunity.confidence * 15.0
        strategic_fit_component = opportunity.strategic_fit * 15.0

        total = (
            value_component
            + effort_component
            + risk_component
            + confidence_component
            + strategic_fit_component
        )

        return OpportunityScore(
            opportunity_id=opportunity.opportunity_id,
            score=round(total, 4),
            value_component=round(value_component, 4),
            effort_component=round(effort_component, 4),
            risk_component=round(risk_component, 4),
            confidence_component=round(confidence_component, 4),
            strategic_fit_component=round(strategic_fit_component, 4),
        )

    def rank(self, opportunities: Iterable[Opportunity]) -> tuple[OpportunityScore, ...]:
        scores = [self.score(item) for item in opportunities]
        scores.sort(key=lambda item: (-item.score, item.opportunity_id))
        return tuple(scores)


class OpportunityStore:
    """Append-only local JSONL opportunity store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> tuple[Opportunity, ...]:
        if not self.path.exists():
            return ()

        items: list[Opportunity] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid opportunity JSON at line {line_number}"
                ) from exc

            raw["status"] = OpportunityStatus(raw["status"])
            items.append(Opportunity(**raw))

        return tuple(items)

    def get(self, opportunity_id: str) -> Opportunity | None:
        for item in self.all():
            if item.opportunity_id == opportunity_id:
                return item
        return None

    def append(
        self,
        opportunity: Opportunity,
        *,
        timestamp: str | None = None,
    ) -> Opportunity:
        if self.get(opportunity.opportunity_id) is not None:
            raise ValueError(
                f"duplicate opportunity_id: {opportunity.opportunity_id}"
            )

        item = opportunity.with_timestamp(timestamp)
        record = asdict(item)
        record["status"] = item.status.value

        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

        return item
