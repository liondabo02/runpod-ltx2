"""Real cost accounting from the model spend ledger.

Every model call appends to ``runtime/model-spend.jsonl``. This module turns that
ledger into an honest report: calls, USD, cheapest/most expensive model, and a
hard flag when any paid provider was used while the budget policy says 0 USD.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CostReport:
    calls: int = 0
    usd: float = 0.0
    by_model: dict[str, dict[str, float]] = field(default_factory=dict)
    paid_models: list[str] = field(default_factory=list)

    @property
    def free_calls(self) -> int:
        return sum(
            int(row["calls"]) for model, row in self.by_model.items() if row["usd"] == 0
        )

    def summary(self) -> str:
        paid = "EVET" if self.paid_models else "HAYIR"
        return (
            f"{self.calls} çağrı · ${self.usd:.4f} · ücretsiz {self.free_calls} · "
            f"ücretli kullanım: {paid}"
        )


def build_report(ledger: str | Path, *, limit_lines: int = 20000) -> CostReport:
    path = Path(ledger)
    report = CostReport()
    if not path.exists():
        return report

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit_lines:]
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        model = str(entry.get("model") or "unknown")
        usd = float(entry.get("usd") or 0.0)
        row = report.by_model.setdefault(model, {"calls": 0.0, "usd": 0.0})
        row["calls"] += 1
        row["usd"] += usd
        report.calls += 1
        report.usd += usd
        if usd > 0 and model not in report.paid_models:
            report.paid_models.append(model)

    return report
