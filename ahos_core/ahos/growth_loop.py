from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .departments import DepartmentSpec
from .owner_console import ConsoleResult, OwnerConsole, build_default_console

GROWTH_CYCLE: tuple[str, ...] = (
    "haftalık üretim planını güncelle ve ilk üç işi tanımla",
    "satış ve pazarlama hunisini gözden geçir, yeni müşteri kanalı öner",
    "kalite denetimi yap, eksikleri ve riskleri listele",
    "son çıktıları iyileştirmek için somut bir geliştirme planı çıkar",
)


@dataclass(frozen=True, slots=True)
class GrowthTick:
    department_id: str
    department_name: str
    objective: str
    status: str
    message: str
    mission_id: str | None


@dataclass
class GrowthLoop:
    """Deterministic self-improvement loop for every active department.

    Each tick picks the departments with the fewest missions so far and gives
    them the next item of a fixed growth cycle. Every mission goes through the
    same owner console path (queue, manager, worker, QA) - the loop never
    bypasses governance or budgets.
    """

    console: OwnerConsole
    interval_seconds: float = 60.0
    missions_per_tick: int = 1
    only_departments: tuple[str, ...] = ()
    stop_file: Path | None = None
    use_ceo: bool = False
    history: list[GrowthTick] = field(default_factory=list)
    last_throttle: str | None = None

    def __post_init__(self) -> None:
        if self.interval_seconds < 1:
            raise ValueError("interval_seconds must be >= 1")
        if self.missions_per_tick < 1:
            raise ValueError("missions_per_tick must be >= 1")

    # ------------------------------------------------------------------ planning
    def active_departments(self) -> tuple[DepartmentSpec, ...]:
        specs = self.console.book.active()
        if self.only_departments:
            wanted = set(self.only_departments)
            specs = tuple(spec for spec in specs if spec.department_id in wanted)
        return specs

    def mission_count(self, department_id: str) -> int:
        queue = self.console.queue
        if queue is None:
            return 0
        return sum(
            1
            for mission in queue.list()
            if mission.primary_department == department_id
        )

    def next_objective(self, spec: DepartmentSpec) -> str:
        index = self.mission_count(spec.department_id) % len(GROWTH_CYCLE)
        return GROWTH_CYCLE[index]

    def plan_tick(self) -> list[tuple[DepartmentSpec, str]]:
        if self.use_ceo:
            from .holding_office import HoldingOffice

            directive = HoldingOffice(self.console).next_directive()
            if directive is not None:
                spec = self.console.book.get(directive.department_id)
                if spec is not None and spec.is_active:
                    return [(spec, directive.objective)]
            return []

        specs = list(self.active_departments())
        specs.sort(
            key=lambda spec: (
                self.mission_count(spec.department_id),
                spec.department_id,
            )
        )
        return [
            (spec, self.next_objective(spec))
            for spec in specs[: self.missions_per_tick]
        ]

    # ---------------------------------------------------------------- execution
    def run_once(self) -> list[GrowthTick]:
        from .growth_budget import GrowthBudget
        if self.should_stop():
            return []
        budget = GrowthBudget(self.console.runtime_dir / "growth-budget.sqlite3")
        ticks: list[GrowthTick] = []
        self.last_throttle = None
        for spec, objective in self.plan_tick():
            full_objective = (
                objective
                if objective.startswith(spec.name)
                else f"{spec.name}: {objective}"
            )
            reservation, reason = budget.reserve(spec.department_id, full_objective)
            if reservation is None:
                self.last_throttle = reason
                continue
            try:
                result: ConsoleResult = self.console.run_department_mission(spec, full_objective)
            except Exception:
                budget.finish(reservation, "failed")
                raise
            budget.finish(reservation, "completed" if result.status == "routed" else "blocked")
            tick = GrowthTick(
                department_id=spec.department_id,
                department_name=spec.name,
                objective=full_objective,
                status=result.status,
                message=result.message,
                mission_id=result.mission.mission_id if result.mission else None,
            )
            ticks.append(tick)
            self.history.append(tick)
        return ticks

    def should_stop(self) -> bool:
        return bool(self.stop_file and self.stop_file.exists())

    def _wait(self, seconds: float, sleeper: Callable[[float], None]) -> None:
        """Sleep in small slices so a stop request is honoured promptly."""

        remaining = seconds
        while remaining > 0:
            if self.should_stop():
                return
            slice_seconds = min(0.25, remaining)
            sleeper(slice_seconds)
            remaining -= slice_seconds

    def run(
        self,
        *,
        max_ticks: int | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        completed = 0
        while not self.should_stop():
            if max_ticks is not None and completed >= max_ticks:
                return
            self.run_once()
            completed += 1
            if self.should_stop():
                return
            if max_ticks is not None and completed >= max_ticks:
                return
            self._wait(self.interval_seconds, sleeper)

    # ------------------------------------------------------------------ summary
    def status(self) -> dict[str, object]:
        return {
            "interval_seconds": self.interval_seconds,
            "missions_per_tick": self.missions_per_tick,
            "ticks": len(self.history),
            "last_throttle": self.last_throttle,
            "automatic_task_limit_24h": 8,
            "last": (
                {
                    "department_id": self.history[-1].department_id,
                    "objective": self.history[-1].objective,
                    "status": self.history[-1].status,
                    "message": self.history[-1].message,
                }
                if self.history
                else None
            ),
        }


def _default_runtime_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "runtime"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(
        prog="ahos-growth",
        description="Departmanların sürekli gelişim döngüsü.",
    )
    parser.add_argument("--runtime-dir", default=str(_default_runtime_dir()))
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--per-tick", type=int, default=1)
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--department", action="append", default=[])
    args = parser.parse_args(argv)

    console = build_default_console(Path(args.runtime_dir))
    loop = GrowthLoop(
        console,
        interval_seconds=max(1.0, args.interval),
        missions_per_tick=max(1, args.per_tick),
        only_departments=tuple(args.department),
        stop_file=Path(args.runtime_dir) / "growth-loop.stop",
    )

    if args.ticks == 1:
        for tick in loop.run_once():
            print(f"[{tick.status}] {tick.department_name}: {tick.message}")
        return 0

    loop.run(max_ticks=args.ticks)
    print(f"ticks: {len(loop.history)}")
    for tick in loop.history[-5:]:
        print(f"[{tick.status}] {tick.department_name}: {tick.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
