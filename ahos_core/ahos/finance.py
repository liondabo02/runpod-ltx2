from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any


class LedgerEntryType(str, Enum):
    REVENUE = "revenue"
    COST = "cost"
    COMMITMENT = "commitment"
    ALLOCATION = "allocation"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    entry_id: str
    venture_id: str
    entry_type: LedgerEntryType
    amount_usd: Decimal
    category: str
    correlation_id: str
    timestamp: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UnitEconomicsSnapshot:
    venture_id: str
    revenue_usd: Decimal
    cost_usd: Decimal
    commitment_usd: Decimal
    allocation_usd: Decimal
    gross_profit_usd: Decimal
    gross_margin: Decimal | None
    available_allocation_usd: Decimal
    entry_count: int


def _money(value: Decimal | int | float | str) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc
    if amount < 0:
        raise ValueError("money value must be >= 0")
    return amount


class FinancialLedger:
    """Append-only local ledger. No external financial actions are performed."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> tuple[LedgerEntry, ...]:
        if not self.path.exists():
            return ()
        result = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid ledger JSON at line {line_number}") from exc
            result.append(LedgerEntry(
                entry_id=raw["entry_id"],
                venture_id=raw["venture_id"],
                entry_type=LedgerEntryType(raw["entry_type"]),
                amount_usd=_money(raw["amount_usd"]),
                category=raw["category"],
                correlation_id=raw["correlation_id"],
                timestamp=raw["timestamp"],
                metadata=dict(raw.get("metadata", {})),
            ))
        return tuple(result)

    def get(self, entry_id: str) -> LedgerEntry | None:
        return next((e for e in self.entries() if e.entry_id == entry_id), None)

    def append(
        self,
        *,
        entry_id: str,
        venture_id: str,
        entry_type: LedgerEntryType,
        amount_usd: Decimal | int | float | str,
        category: str,
        correlation_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerEntry:
        if not entry_id.strip():
            raise ValueError("entry_id must not be empty")
        if not venture_id.strip():
            raise ValueError("venture_id must not be empty")
        if not category.strip():
            raise ValueError("category must not be empty")
        if self.get(entry_id) is not None:
            raise ValueError(f"duplicate entry_id: {entry_id}")

        entry = LedgerEntry(
            entry_id=entry_id,
            venture_id=venture_id,
            entry_type=entry_type,
            amount_usd=_money(amount_usd),
            category=category,
            correlation_id=correlation_id or f"venture:{venture_id}",
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            metadata=dict(metadata or {}),
        )
        record = asdict(entry)
        record["entry_type"] = entry.entry_type.value
        record["amount_usd"] = format(entry.amount_usd, "f")
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        return entry

    def snapshot(self, venture_id: str) -> UnitEconomicsSnapshot:
        entries = tuple(e for e in self.entries() if e.venture_id == venture_id)
        totals = {kind: Decimal("0.00") for kind in LedgerEntryType}
        for entry in entries:
            totals[entry.entry_type] += entry.amount_usd

        revenue = totals[LedgerEntryType.REVENUE].quantize(Decimal("0.01"))
        cost = totals[LedgerEntryType.COST].quantize(Decimal("0.01"))
        commitment = totals[LedgerEntryType.COMMITMENT].quantize(Decimal("0.01"))
        allocation = totals[LedgerEntryType.ALLOCATION].quantize(Decimal("0.01"))
        gross_profit = (revenue - cost).quantize(Decimal("0.01"))
        gross_margin = None if revenue == 0 else (gross_profit / revenue).quantize(Decimal("0.0001"))
        available = (allocation - cost - commitment).quantize(Decimal("0.01"))

        return UnitEconomicsSnapshot(
            venture_id=venture_id,
            revenue_usd=revenue,
            cost_usd=cost,
            commitment_usd=commitment,
            allocation_usd=allocation,
            gross_profit_usd=gross_profit,
            gross_margin=gross_margin,
            available_allocation_usd=available,
            entry_count=len(entries),
        )
