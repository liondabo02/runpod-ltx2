from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class FaultResult:
    name: str
    recovered: bool
    detail: str


class FaultInjectionHarness:
    """Deterministic local test harness; never touches external systems itself."""

    def run(self, name: str, fault: Callable[[], None], recovery_check: Callable[[], bool]) -> FaultResult:
        if not name:
            raise ValueError("name required")
        detail = ""
        try:
            fault()
        except Exception as exc:
            detail = type(exc).__name__
        recovered = bool(recovery_check())
        return FaultResult(name, recovered, detail)
