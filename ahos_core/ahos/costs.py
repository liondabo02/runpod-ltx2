from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class CostGuard:
    daily_budget_usd: float
    spent_usd: float = 0.0
    day: date = date.today()

    def _roll_day(self) -> None:
        today = date.today()
        if today != self.day:
            self.day = today
            self.spent_usd = 0.0

    def can_spend(self, amount_usd: float) -> bool:
        self._roll_day()
        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        return self.spent_usd + amount_usd <= self.daily_budget_usd

    def record(self, amount_usd: float) -> None:
        self._roll_day()
        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        if not self.can_spend(amount_usd):
            raise RuntimeError("daily budget would be exceeded")
        self.spent_usd += amount_usd
