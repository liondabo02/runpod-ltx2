"""Always-on supervised host for the bounded autonomy scheduler.

The scheduler decides *whether* a mission may run; the daemon decides *when the
scheduler is allowed to tick* and keeps that decision observable. It is a plain
process, not a thread inside the panel, so a panel restart never stops the
holding and a crashed daemon never takes the panel down with it.

Safety contract:

* single instance per runtime directory (pid file + liveness check),
* one mission at a time (delegated to :class:`ahos.autoschedule.BoundedScheduler`),
* hourly and total quotas, kill-switch and pause files honoured by the scheduler,
* heartbeat file written on every tick so the panel and the operator can see
  that the loop is alive, when it last ran and why it is waiting,
* graceful shutdown on SIGINT/SIGTERM or on ``daemon.stop``,
* no model call, no mission and no queue write while the loop is idle.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .delivery import DeliveryTracker, TreeSnapshot
from .errors import ErrorLog, default_error_log

HEARTBEAT_FILE = "daemon-state.json"
PID_FILE = "daemon.pid"
STOP_FILE = "daemon.stop"
MISSIONS_FILE = "daemon-missions.jsonl"
SCHEMA_VERSION = 1

_CHANGED_FILES = re.compile(r"(\d+)\s+dosya değişti")


def mission_evidence(result: object) -> dict[str, object]:
    """Extract the only claim that matters: did the worker change real files?

    The manager/worker summaries are the production record; a mission that was
    routed but changed zero files is a report, not a delivery. This is a
    coarse but honest signal, so the loop can stop instead of celebrating
    documents as progress.
    """

    mission = getattr(result, "mission", None)
    steps = tuple(getattr(mission, "steps", ()) or ()) if mission is not None else ()
    changed = 0
    for step in steps:
        summary = str(getattr(step, "worker_summary", "") or "")
        for match in _CHANGED_FILES.finditer(summary):
            changed += int(match.group(1))
    return {
        "mission_id": str(getattr(mission, "mission_id", "") or ""),
        "status": str(getattr(result, "status", "") or ""),
        "steps": len(steps),
        "changed_files": changed,
        "evidence_ok": changed > 0,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_runtime_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "runtime"


def read_heartbeat(runtime_dir: str | Path) -> dict[str, object]:
    """Read the persisted heartbeat without constructing a scheduler."""

    try:
        return json.loads((Path(runtime_dir) / HEARTBEAT_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness probe that never sends a signal on Windows."""

    if pid <= 0:
        return False
    if os.name == "nt":  # pragma: no cover - platform specific
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class SchedulerLike(Protocol):
    def tick(self) -> str: ...


def available_ram_bytes() -> int:
    """Best-effort free physical memory (0 when unknown)."""

    try:
        import ctypes

        class Memory(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("load", ctypes.c_ulong),
            ] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "total",
                    "available",
                    "total_page",
                    "available_page",
                    "total_virtual",
                    "available_virtual",
                    "extended",
                )
            ]

        state = Memory()
        state.length = ctypes.sizeof(state)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return 0
        return int(state.available)
    except Exception:  # pragma: no cover - non-Windows / restricted
        return 0


def _model_is_configured() -> bool:
    try:
        from .llm_executor import load_settings

        return load_settings() is not None
    except Exception:  # pragma: no cover - defensive
        return False


@dataclass
class DaemonState:
    """Persisted heartbeat; every field is derived from real observations."""

    pid: int = 0
    started_at: str = ""
    last_tick_at: str = ""
    ticks: int = 0
    status: str = "starting"
    last_reason: str = ""
    interval_seconds: float = 0.0
    scheduler: dict[str, object] = field(default_factory=dict)
    last_evidence: dict[str, object] = field(default_factory=dict)
    no_evidence_streak: int = 0
    executor_mode: str = ""
    executor_reason: str = ""
    schema: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "pid": self.pid,
            "started_at": self.started_at,
            "last_tick_at": self.last_tick_at,
            "ticks": self.ticks,
            "status": self.status,
            "last_reason": self.last_reason,
            "interval_seconds": self.interval_seconds,
            "scheduler": dict(self.scheduler),
            "last_evidence": dict(self.last_evidence),
            "no_evidence_streak": self.no_evidence_streak,
            "executor_mode": self.executor_mode,
            "executor_reason": self.executor_reason,
        }


class RecordingRunner:
    """Proxy that remembers the last mission result for the evidence gate."""

    def __init__(self, runner: object) -> None:
        self._runner = runner
        self.last_result: object | None = None

    def run_once(self):  # noqa: ANN201 - mirrors AutonomyRunner.run_once
        self.last_result = self._runner.run_once()  # type: ignore[attr-defined]
        return self.last_result

    def __getattr__(self, name: str):
        return getattr(self._runner, name)


class AutonomyDaemon:
    """Host one bounded scheduler in a supervised, observable loop."""

    def __init__(
        self,
        scheduler: SchedulerLike,
        runtime_dir: str | Path,
        *,
        interval_seconds: float = 60.0,
        wall_clock: Callable[[], str] = _now,
        sleep: Callable[[float], None] = time.sleep,
        max_ticks: int | None = None,
        no_evidence_limit: int = 3,
        tracker: DeliveryTracker | None = None,
        executor_mode: str = "auto",
        ram_probe: Callable[[], int] = available_ram_bytes,
        model_ram_floor: int = 2 * 1024**3,
        error_log: ErrorLog | None = None,
    ) -> None:
        if interval_seconds < 1:
            raise ValueError("interval_seconds >= 1 olmalı")
        if max_ticks is not None and max_ticks < 1:
            raise ValueError("max_ticks >= 1 olmalı")
        if no_evidence_limit < 0:
            raise ValueError("no_evidence_limit >= 0 olmalı")
        if executor_mode not in {"auto", "deterministic", "model"}:
            raise ValueError("executor_mode auto|deterministic|model olmalı")
        self.scheduler = scheduler
        self.runtime_dir = Path(runtime_dir)
        self.interval_seconds = float(interval_seconds)
        self.wall_clock = wall_clock
        self.sleep = sleep
        self.max_ticks = max_ticks
        self.no_evidence_limit = no_evidence_limit
        self.tracker = tracker
        self.executor_mode = executor_mode
        self.ram_probe = ram_probe
        self.model_ram_floor = int(model_ram_floor)
        self.error_log = error_log or default_error_log(self.runtime_dir)
        self.state = DaemonState(interval_seconds=self.interval_seconds)
        self._stop_requested = False
        self._last_recorded_mission = ""

    # ------------------------------------------------------------- file layout
    @property
    def heartbeat_path(self) -> Path:
        return self.runtime_dir / HEARTBEAT_FILE

    @property
    def pid_path(self) -> Path:
        return self.runtime_dir / PID_FILE

    @property
    def stop_path(self) -> Path:
        return self.runtime_dir / STOP_FILE

    # ----------------------------------------------------------- single instance
    def current_pid(self) -> int:
        """Return the pid of a live daemon, or 0 when the runtime is free."""

        try:
            payload = json.loads(self.pid_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        try:
            pid = int(payload.get("pid") or 0)
        except (TypeError, ValueError):
            return 0
        if pid and pid != os.getpid() and _pid_alive(pid):
            return pid
        return 0

    def acquire(self) -> tuple[bool, int]:
        """Claim the runtime directory; refuse when another daemon is alive."""

        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        other = self.current_pid()
        if other:
            return False, other
        payload = {"pid": os.getpid(), "started_at": self.wall_clock()}
        tmp = self.pid_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, self.pid_path)
        self.state.pid = os.getpid()
        self.state.started_at = payload["started_at"]
        return True, os.getpid()

    def release(self) -> None:
        try:
            payload = json.loads(self.pid_path.read_text(encoding="utf-8"))
            if int(payload.get("pid") or 0) == os.getpid():
                self.pid_path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    # --------------------------------------------------------------- heartbeat
    def _scheduler_snapshot(self) -> dict[str, object]:
        state = getattr(self.scheduler, "state", None)
        if state is None:
            return {}
        try:
            return {
                "status": getattr(state, "status", ""),
                "hour_key": getattr(state, "hour_key", ""),
                "missions_this_hour": getattr(state, "missions_this_hour", 0),
                "missions_total": getattr(state, "missions_total", 0),
                "last_reason": getattr(state, "last_reason", ""),
            }
        except Exception:  # pragma: no cover - heartbeat must never break the loop
            return {}

    def write_heartbeat(self) -> None:
        self.state.scheduler = self._scheduler_snapshot()
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.heartbeat_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self.state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self.heartbeat_path)

    def read_heartbeat(self) -> dict[str, object]:
        try:
            return json.loads(self.heartbeat_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # ------------------------------------------------------------------- ticks
    def _append_mission(self, evidence: dict[str, object]) -> None:
        path = self.runtime_dir / MISSIONS_FILE
        record = {"at": self.wall_clock(), **evidence}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _record_evidence(self, filesystem: dict[str, object] | None = None) -> None:
        """Refuse to count report-only missions as progress.

        The filesystem delta is authoritative when project roots are known; the
        worker summary is only a fallback. Autonomy stops itself after
        ``no_evidence_limit`` consecutive missions that were routed but changed
        no files, so a document factory can never masquerade as a self-improving
        holding.
        """

        runner = getattr(self.scheduler, "runner", None)
        result = getattr(runner, "last_result", None)
        if result is None:
            return
        evidence = mission_evidence(result)
        mission_id = str(evidence.get("mission_id") or "")
        if not mission_id or mission_id == self._last_recorded_mission:
            return
        self._last_recorded_mission = mission_id
        if filesystem is not None and self.tracker is not None and self.tracker.roots():
            evidence["changed_files"] = int(filesystem.get("changed_files") or 0)
            evidence["projects"] = filesystem.get("projects") or []
            evidence["source"] = "filesystem"
            evidence["evidence_ok"] = bool(evidence["changed_files"])
        else:
            evidence["source"] = "worker-summary"
        self.state.last_evidence = evidence
        self._append_mission(evidence)
        if evidence.get("status") == "routed" and not evidence.get("evidence_ok"):
            self.state.no_evidence_streak += 1
        else:
            self.state.no_evidence_streak = 0
        if self.no_evidence_limit and (
            self.state.no_evidence_streak >= self.no_evidence_limit
        ):
            (self.runtime_dir / "autonomy.pause").write_text(
                self.wall_clock(), encoding="utf-8"
            )
            self.state.status = "paused_no_evidence"
            self.state.last_reason = (
                f"{self.state.no_evidence_streak} art arda kanıtsız görev; "
                "döngü durduruldu (autonomy.pause)"
            )

    def _apply_executor_mode(self) -> None:
        """Pick the worker implementation for the next mission, honestly.

        The local model path refuses to run below 2 GiB of free RAM, so a
        holding that always asked for the model would fail every mission on a
        busy machine. In ``auto`` mode the daemon uses the model only when it
        is configured *and* there is memory for it; otherwise it keeps the
        deterministic project worker, which still edits files and passes QA.
        """

        if self.executor_mode == "deterministic":
            os.environ["AHOS_EXECUTOR"] = "deterministic"
            self.state.executor_mode = "deterministic"
            self.state.executor_reason = "sabit (deterministik) mod"
            return
        if self.executor_mode == "model":
            os.environ["AHOS_EXECUTOR"] = "model"
            self.state.executor_mode = "model"
            self.state.executor_reason = "elle model modu"
            return
        free = int(self.ram_probe() or 0)
        floor = self.model_ram_floor
        if _model_is_configured() and free >= floor:
            os.environ["AHOS_EXECUTOR"] = "model"
            self.state.executor_mode = "model"
            self.state.executor_reason = (
                f"RAM {free // (1024 ** 2)} MiB >= {floor // (1024 ** 2)} MiB"
            )
        else:
            os.environ["AHOS_EXECUTOR"] = "deterministic"
            self.state.executor_mode = "deterministic"
            self.state.executor_reason = (
                "model yapılandırılmadı"
                if not _model_is_configured()
                else f"RAM {free // (1024 ** 2)} MiB < {floor // (1024 ** 2)} MiB"
            )

    def tick_once(self) -> str:
        """Run exactly one scheduler tick and persist the result."""

        self._apply_executor_mode()
        before: dict[str, TreeSnapshot] | None = None
        if self.tracker is not None and self.tracker.roots():
            before = self.tracker.snapshot()
        status = str(self.scheduler.tick())
        filesystem = None
        if before is not None and self.tracker is not None:
            filesystem = self.tracker.diff(before, self.tracker.snapshot())
        self.state.ticks += 1
        self.state.last_tick_at = self.wall_clock()
        self.state.status = status
        self.state.last_reason = str(
            getattr(getattr(self.scheduler, "state", None), "last_reason", "") or ""
        )[:200]
        self._record_evidence(filesystem)
        self.write_heartbeat()
        return status

    def request_stop(self) -> None:
        self._stop_requested = True

    def _should_stop(self) -> bool:
        if self._stop_requested or self.stop_path.exists():
            return True
        return self.max_ticks is not None and self.state.ticks >= self.max_ticks

    def _sleep(self) -> None:
        """Sleep in small slices so a stop request is honoured quickly."""

        remaining = self.interval_seconds
        while remaining > 0 and not self._stop_requested:
            slice_seconds = min(5.0, remaining)
            self.sleep(slice_seconds)
            remaining -= slice_seconds

    def run(self) -> int:
        """Tick until stopped; returns the process exit code."""

        acquired, pid = self.acquire()
        if not acquired:
            print(f"AHOS daemon zaten çalışıyor (pid {pid}); yeni süreç başlatılmadı.")
            return 2
        self.write_heartbeat()
        try:
            while not self._should_stop():
                try:
                    self.tick_once()
                except Exception as exc:  # the loop must survive a bad mission
                    self.state.status = "error"
                    self.state.last_reason = f"{type(exc).__name__}: {exc}"[:200]
                    self.state.last_tick_at = self.wall_clock()
                    try:
                        self.error_log.record(
                            "daemon.tick",
                            exc,
                            context={"ticks": self.state.ticks},
                        )
                    except Exception:  # pragma: no cover - logging must not stop the loop
                        pass
                    self.write_heartbeat()
                if self._should_stop():
                    break
                self._sleep()
        finally:
            self.state.status = "stopped"
            self.write_heartbeat()
            self.release()
        return 0


def build_default_daemon(
    runtime_dir: str | Path,
    *,
    interval_seconds: float = 60.0,
    missions_per_hour: int = 2,
    missions_total: int = 6,
    no_evidence_limit: int = 3,
) -> AutonomyDaemon:
    """Wire the real console, autonomy runner and bounded scheduler."""

    from .autonomy import AutonomyLimits, AutonomyRunner
    from .autoschedule import AutoLimits, BoundedScheduler
    from .owner_console import build_default_console

    runtime = Path(runtime_dir)
    console = build_default_console(runtime)
    runner = RecordingRunner(
        AutonomyRunner(
            console,
            runtime,
            # The scheduler owns the global quota; the runner only guards one run.
            limits=AutonomyLimits(max_missions=max(1, missions_per_hour)),
        )
    )
    scheduler = BoundedScheduler(
        runner,
        runtime,
        limits=AutoLimits(
            max_missions_per_hour=max(1, missions_per_hour),
            max_missions_total=max(1, missions_total),
            idle_sleep_seconds=interval_seconds,
        ),
    )
    tracker = DeliveryTracker([link.path for link in console.projects.all()])
    return AutonomyDaemon(
        scheduler,
        runtime,
        interval_seconds=interval_seconds,
        no_evidence_limit=no_evidence_limit,
        tracker=tracker,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - odd console
        pass

    parser = argparse.ArgumentParser(
        prog="ahos-daemon",
        description="AHOS otonomi döngüsünü her zaman açık, sınırlı ve gözlenebilir tutar.",
    )
    parser.add_argument("--runtime-dir", default=str(_default_runtime_dir()))
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--missions-per-hour", type=int, default=2)
    parser.add_argument("--missions-total", type=int, default=6)
    parser.add_argument(
        "--executor-mode",
        choices=("auto", "deterministic", "model"),
        default="auto",
        help="auto: RAM ve yapılandırma uygunsa yerel model, değilse deterministik işçi",
    )
    parser.add_argument(
        "--no-evidence-limit",
        type=int,
        default=3,
        help="art arda bu kadar kanıtsız (dosya değiştirmeyen) görevden sonra dur",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="test/teşhis için: bu kadar tick sonra temiz çık",
    )
    parser.add_argument("--status", action="store_true", help="yalnız durumu yazdır")
    parser.add_argument("--stop", action="store_true", help="çalışan daemon'a durma sinyali bırak")
    args = parser.parse_args(argv)

    runtime = Path(args.runtime_dir)
    if args.status:
        heartbeat = read_heartbeat(runtime)
        print(json.dumps(heartbeat or {"status": "not-running"}, indent=2, ensure_ascii=False))
        return 0
    if args.stop:
        (runtime / STOP_FILE).write_text(_now(), encoding="utf-8")
        print("durma sinyali bırakıldı")
        return 0

    daemon = build_default_daemon(
        runtime,
        interval_seconds=args.interval_seconds,
        missions_per_hour=args.missions_per_hour,
        missions_total=args.missions_total,
        no_evidence_limit=args.no_evidence_limit,
    )
    daemon.executor_mode = args.executor_mode
    daemon.max_ticks = args.max_ticks

    def _handle(signum, _frame):
        daemon.request_stop()

    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is not None:
            try:
                signal.signal(sig, _handle)
            except (OSError, ValueError):  # pragma: no cover - non-main thread
                pass

    return daemon.run()


if __name__ == "__main__":
    raise SystemExit(main())
