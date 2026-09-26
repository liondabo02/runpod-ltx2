from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .autonomous_company import CompanyLoop


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class CompanyService:
    loop: CompanyLoop
    heartbeat_path: Path
    stop_path: Path
    poll_seconds: float = 2.0
    automation_steps: tuple[Callable[[], str], ...] = ()

    def __post_init__(self) -> None:
        self.heartbeat_path = Path(self.heartbeat_path)
        self.stop_path = Path(self.stop_path)
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        self.stop_path.parent.mkdir(parents=True, exist_ok=True)

    def write_heartbeat(self, state: str, **extra: object) -> None:
        payload = {"timestamp": _utc_now(), "pid": os.getpid(), "state": state, **extra}
        tmp = self.heartbeat_path.with_suffix(self.heartbeat_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.heartbeat_path)

    def should_stop(self) -> bool:
        return self.stop_path.exists()

    def run_once(self) -> str:
        self.write_heartbeat("polling")
        automation_results: list[str] = []
        for step in self.automation_steps:
            automation_results.append(str(step()))
        mission = self.loop.run_once()
        if mission is None:
            self.write_heartbeat("idle", automation_results=automation_results)
            return "idle"
        self.write_heartbeat(
            "processed",
            mission_id=mission.mission_id,
            mission_status=mission.status.value,
            attempts=mission.attempts,
            automation_results=automation_results,
        )
        return mission.status.value

    def run_forever(self) -> None:
        self.write_heartbeat("starting")
        while not self.should_stop():
            try:
                state = self.run_once()
            except Exception as exc:
                self.write_heartbeat("error", error=f"{type(exc).__name__}: {exc}")
                time.sleep(self.poll_seconds)
                continue
            if state == "idle":
                time.sleep(self.poll_seconds)
        self.write_heartbeat("stopped")
