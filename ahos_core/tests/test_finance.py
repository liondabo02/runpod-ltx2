from decimal import Decimal

import pytest

from ahos.finance import FinancialLedger, LedgerEntryType


def test_round_trip_and_duplicate_protection(tmp_path):
    ledger = FinancialLedger(tmp_path / "ledger.jsonl")
    entry = ledger.append(
        entry_id="e-1",
        venture_id="v-1",
        entry_type=LedgerEntryType.ALLOCATION,
        amount_usd="1000",
        category="budget",
        timestamp="2026-09-16T12:00:00+00:00",
    )
    assert FinancialLedger(tmp_path / "ledger.jsonl").get("e-1") == entry
    with pytest.raises(ValueError, match="duplicate entry_id"):
        ledger.append(
            entry_id="e-1",
            venture_id="v-1",
            entry_type=LedgerEntryType.COST,
            amount_usd="10",
            category="duplicate",
        )


def test_negative_amount_rejected(tmp_path):
    ledger = FinancialLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="must be >= 0"):
        ledger.append(
            entry_id="bad",
            venture_id="v-1",
            entry_type=LedgerEntryType.COST,
            amount_usd="-1",
            category="bad",
        )


def test_unit_economics_snapshot(tmp_path):
    ledger = FinancialLedger(tmp_path / "ledger.jsonl")
    rows = [
        ("a", LedgerEntryType.ALLOCATION, "2000", "budget"),
        ("r", LedgerEntryType.REVENUE, "1200", "sales"),
        ("c", LedgerEntryType.COST, "300", "ops"),
        ("m", LedgerEntryType.COMMITMENT, "250", "reserved"),
    ]
    for entry_id, kind, amount, category in rows:
        ledger.append(
            entry_id=entry_id,
            venture_id="v-1",
            entry_type=kind,
            amount_usd=amount,
            category=category,
        )

    s = ledger.snapshot("v-1")
    assert s.revenue_usd == Decimal("1200.00")
    assert s.cost_usd == Decimal("300.00")
    assert s.gross_profit_usd == Decimal("900.00")
    assert s.gross_margin == Decimal("0.7500")
    assert s.available_allocation_usd == Decimal("1450.00")
    assert s.entry_count == 4


def test_snapshot_is_venture_scoped(tmp_path):
    ledger = FinancialLedger(tmp_path / "ledger.jsonl")
    ledger.append(entry_id="1", venture_id="v-1", entry_type=LedgerEntryType.REVENUE, amount_usd="100", category="sales")
    ledger.append(entry_id="2", venture_id="v-2", entry_type=LedgerEntryType.REVENUE, amount_usd="900", category="sales")
    assert ledger.snapshot("v-1").revenue_usd == Decimal("100.00")


def test_zero_revenue_margin_is_none(tmp_path):
    ledger = FinancialLedger(tmp_path / "ledger.jsonl")
    ledger.append(entry_id="1", venture_id="v-1", entry_type=LedgerEntryType.COST, amount_usd="25", category="test")
    s = ledger.snapshot("v-1")
    assert s.gross_margin is None
    assert s.gross_profit_usd == Decimal("-25.00")
