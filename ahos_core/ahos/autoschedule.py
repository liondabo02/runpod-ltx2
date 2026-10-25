"""Bounded autonomous scheduler (quota + idle sleep + kill-switch aware).

This sits *above* :class:`ahos.autonomy.AutonomyRunner`: the runner executes one
mission, the scheduler decides when it may run. It never spins, never calls a
model when the queue is empty, and stops on the existing pause / kill-switch
files.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import audit


@dataclass(frozen=True)
class AutoLimits:
    max_missions_per_hour: int = 6
    max_missions_total: int = 20
    max_usd_per_hour: float = 0.0
    idle_sleep_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_missions_per_hour < 1:
            raise ValueError("max_missions_per_hour >= 1 olmalı")
        if self.max_missions_total < 1:
            raise ValueError("max_missions_total >= 1 olmalı")
        if self.max_usd_per_hour != 0:
            raise ValueError("ücretli bütçe kapalı olmalı (max_usd_per_hour=0)")


@dataclass
class AutoState:
    hour_key: str = ""
    missions_this_hour: int = 0
    missions_total: int = 0
    status: str = "idle"
    last_reason: str = ""
    updated_at: str = ""
    missions: list[str] = field(default_factory=list)


class BoundedScheduler:
    def __init__(
        self,
        runner,
        runtime_dir: str | Path,
        *,
        limits: AutoLimits | None = None,
        wall_clock=lambda: datetime.now(timezone.utc),
        sleep=time.sleep,
    ) -> None:
        self.runner = runner
        self.runtime_dir = Path(runtime_dir)
        self.limits = limits or AutoLimits()
        self.wall_clock = wall_clock
        self.sleep = sleep
        self.state = AutoState()
        self._load()

    # ------------------------------------------------------------ persistence
    def _path(self) -> Path:
        return self.runtime_dir / "auto-scheduler-state.json"

    def _load(self) -> None:
        path = self._path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        raw_missions = list(payload.get("missions") or [])
        unique_missions = list(dict.fromkeys(item for item in raw_missions if item))
        self.state = AutoState(
            hour_key=str(payload.get("hour_key") or ""),
            missions_this_hour=len(unique_missions),
            missions_total=int(payload.get("missions_total") or 0),
            status=str(payload.get("status") or "idle"),
            last_reason=str(payload.get("last_reason") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            missions=unique_missions,
        )

    def _save(self) -> None:
        self.state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.state.__dict__, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _roll_hour(self) -> None:
        key = self.wall_clock().strftime("%Y-%m-%dT%H")
        if key != self.state.hour_key:
            self.state.hour_key = key
            self.state.missions_this_hour = 0

    def _blocked_reason(self) -> str | None:
        if (self.runtime_dir / "autonomy.stop").exists():
            return "kill-switch aktif"
        if (self.runtime_dir / "autonomy.pause").exists():
            return "duraklatıldı"
        return None

    # ----------------------------------------------------------------- ticks
    def tick(self) -> str:
        self._roll_hour()
        blocked = self._blocked_reason()
        if blocked:
            self.state.status = "stopped" if "kill" in blocked else "paused"
            self.state.last_reason = blocked
            self._save()
            return self.state.status

        if self.state.missions_total >= self.limits.max_missions_total:
            self.state.status = "stopped"
            self.state.last_reason = "oturum görev limiti doldu"
            self._save()
            return self.state.status

        if self.state.missions_this_hour >= self.limits.max_missions_per_hour:
            self.state.status = "quota_wait"
            self.state.last_reason = "saatlik kota doldu; beklemede"
            self._save()
            return self.state.status

        result = self.runner.run_once()
        if result is None:
            self.state.status = "idle"
            self.state.last_reason = "uygun görev yok; bekleme"
            self._save()
            return self.state.status

        mission = getattr(result, "mission", None)
        mission_id = getattr(mission, "mission_id", "") or ""
        status = getattr(result, "status", "unknown")
        # Aynı görev kimliği tekrar sayılmaz: eski kilit döngüleri kotayı
        # şişiriyordu ve sistem gereksiz yere "kota doldu" diyordu.
        if mission_id and mission_id in self.state.missions:
            self.state.status = "running"
            self.state.last_reason = f"{mission_id}: {status} (tekrar, sayılmadı)"
            self._save()
            return self.state.status
        if mission_id:
            self.state.missions.append(mission_id)
            self.state.missions_this_hour += 1
        self.state.missions_total += 1
        self.state.status = "running"
        self.state.last_reason = f"{mission_id}: {status}"
        self._save()
        try:
            from .audit import AuditLog

            AuditLog(self.runtime_dir / "audit.jsonl").append(
                "scheduler.mission",
                {
                    "mission_id": mission_id,
                    "status": status,
                    "hour_key": self.state.hour_key,
                    "missions_this_hour": self.state.missions_this_hour,
                },
                correlation_id=mission_id or "scheduler",
            )
        except Exception:  # pragma: no cover - audit must never break the loop
            pass
        return self.state.status

    def run(self, *, max_ticks: int = 10) -> list[str]:
        outcomes: list[str] = []
        for _ in range(max(1, max_ticks)):
            status = self.tick()
            outcomes.append(status)
            if status in {"stopped", "paused"}:
                break
            if status in {"idle", "quota_wait"}:
                self.sleep(self.limits.idle_sleep_seconds)
                break
        return outcomes
