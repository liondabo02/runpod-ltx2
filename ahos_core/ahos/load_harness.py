from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable


@dataclass(frozen=True, slots=True)
class LoadReport:
    operations: int
    failures: int
    elapsed_seconds: float
    ops_per_second: float


class LoadHarness:
    def run(self, operation: Callable[[int], None], *, operations: int) -> LoadReport:
        if operations <= 0:
            raise ValueError("operations must be positive")
        failures = 0
        start = perf_counter()
        for index in range(operations):
            try:
                operation(index)
            except Exception:
                failures += 1
        elapsed = max(perf_counter() - start, 1e-9)
        return LoadReport(operations, failures, elapsed, operations / elapsed)
