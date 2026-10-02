from __future__ import annotations

import hashlib
import argparse
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator, Mapping

from .studio_approval import StudioApprovalError, _atomic_write, _hash, _read_object


STAGES = ("render", "tts_7_languages", "mix", "assemble", "delivery_qa")


class StudioExecutionError(RuntimeError):
    pass


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StageResult:
    artifacts: tuple[str, ...]
    cost_usd: float = 0.0
    detail: str = "completed"


StageHandler = Callable[[Path, Mapping[str, object]], StageResult]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StudioExecutionStore:
    def __init__(self, studio_directory: str | Path) -> None:
        self.studio = Path(studio_directory).resolve()
        self.path = self.studio / "EXECUTION-LEDGER.json"
        self.lock = self.studio / ".execution.lock"

    @contextmanager
    def locked(self, timeout: float = 5.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()}\n".encode("ascii"))
                os.close(fd)
                break
            except FileExistsError:
                try:
                    owner = int(self.lock.read_text(encoding="ascii").strip())
                    owner_alive = self._pid_alive(owner)
                    if not owner_alive and time.time() - self.lock.stat().st_mtime > 1:
                        self.lock.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                except (OSError, ValueError):
                    owner_alive = True
                if time.monotonic() >= deadline:
                    raise StudioExecutionError("another studio executor owns the episode lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            self.lock.unlink(missing_ok=True)

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except (PermissionError, OSError):
            return True
        return True

    def read(self) -> dict[str, object] | None:
        return _read_object(self.path) if self.path.exists() else None

    def write(self, value: Mapping[str, object]) -> None:
        _atomic_write(self.path, dict(value))


class StudioExecutor:
    """Resumable, budget-bound owner-approved studio state machine.

    Providers are injected stage handlers. This class owns orchestration and
    evidence only; it cannot publish and it never enables a provider itself.
    """

    def __init__(self, studio_directory: str | Path, handlers: Mapping[str, StageHandler],
                 *, stage_cost_estimates: Mapping[str, float] | None = None) -> None:
        self.store = StudioExecutionStore(studio_directory)
        unknown = set(handlers) - set(STAGES)
        if unknown:
            raise ValueError(f"unknown studio stages: {sorted(unknown)}")
        self.handlers = dict(handlers)
        self.stage_cost_estimates = dict(stage_cost_estimates or {})
        if set(self.stage_cost_estimates) - set(STAGES):
            raise ValueError("cost estimate contains an unknown studio stage")
        if any(float(value) < 0 for value in self.stage_cost_estimates.values()):
            raise ValueError("stage cost estimates must not be negative")

    def initialize(self) -> dict[str, object]:
        with self.store.locked():
            existing = self.store.read()
            if existing is not None:
                return existing
            decision = self._verified_decision()
            preflight = _read_object(self.store.studio / "EXECUTION-PREFLIGHT.json")
            if preflight.get("approval_ready") is not True:
                raise StudioExecutionError("execution preflight has blockers")
            if preflight.get("episode_id") != decision.get("episode_id"):
                raise StudioExecutionError("preflight episode does not match owner decision")
            recommended = float((preflight.get("cost_estimate") or {}).get("recommended_budget_ceiling", 0))
            budget = float(decision["max_budget_usd"])
            if recommended <= 0 or recommended > budget:
                raise StudioExecutionError("preflight estimate exceeds owner budget")
            ledger: dict[str, object] = {
                "schema": "ahos.studio-execution-ledger.v1",
                "execution_id": uuid.uuid4().hex,
                "episode_id": decision["episode_id"],
                "decision_hash": decision["decision_hash"],
                "preflight_sha256": _sha(self.store.studio / "EXECUTION-PREFLIGHT.json"),
                "budget_ceiling_usd": budget,
                "spent_usd": 0.0,
                "status": "running",
                "publishing_enabled": False,
                "stages": {name: {"status": StageStatus.PENDING.value, "attempts": 0,
                                    "artifacts": [], "cost_usd": 0.0, "detail": None}
                           for name in STAGES},
                "created_at": _now(),
                "updated_at": _now(),
            }
            self.store.write(ledger)
            return ledger

    def run_once(self) -> dict[str, object]:
        with self.store.locked():
            ledger = self.store.read()
            if ledger is None:
                raise StudioExecutionError("initialize the execution first")
            self._verify_ledger_binding(ledger)
            stages = ledger["stages"]
            assert isinstance(stages, dict)
            stage_name = next((name for name in STAGES if stages[name]["status"] != "completed"), None)
            if stage_name is None:
                ledger["status"] = "awaiting_final_owner_release"
                ledger["updated_at"] = _now()
                self.store.write(ledger)
                return ledger
            handler = self.handlers.get(stage_name)
            if handler is None:
                ledger["status"] = "blocked"
                stages[stage_name]["detail"] = "stage handler is not configured"
                ledger["updated_at"] = _now()
                self.store.write(ledger)
                return ledger
            if stage_name not in self.stage_cost_estimates:
                ledger["status"] = "blocked"
                stages[stage_name]["detail"] = "stage cost estimate is not configured"
                ledger["updated_at"] = _now()
                self.store.write(ledger)
                return ledger
            estimated_cost = float(self.stage_cost_estimates[stage_name])
            if float(ledger["spent_usd"]) + estimated_cost > float(ledger["budget_ceiling_usd"]):
                ledger["status"] = "blocked"
                stages[stage_name]["detail"] = "stage reservation would exceed owner budget"
                ledger["updated_at"] = _now()
                self.store.write(ledger)
                return ledger
            stage = stages[stage_name]
            if int(stage["attempts"]) >= 3:
                ledger["status"] = "blocked"
                stage["status"] = StageStatus.FAILED.value
                stage["detail"] = "retry limit exhausted"
                self.store.write(ledger)
                return ledger
            stage["status"] = StageStatus.RUNNING.value
            stage["attempts"] = int(stage["attempts"]) + 1
            self.store.write(ledger)
            try:
                result = handler(self.store.studio, ledger)
                if result.cost_usd < 0:
                    raise StudioExecutionError("stage returned negative cost")
                projected = round(float(ledger["spent_usd"]) + result.cost_usd, 6)
                if projected > float(ledger["budget_ceiling_usd"]):
                    raise StudioExecutionError("stage cost would exceed owner budget")
                if result.cost_usd > estimated_cost:
                    raise StudioExecutionError("stage cost exceeded its pre-call reservation")
                artifacts = self._verify_artifacts(result.artifacts)
                stage.update({"status": StageStatus.COMPLETED.value,
                              "artifacts": artifacts, "cost_usd": result.cost_usd,
                              "detail": result.detail, "completed_at": _now()})
                ledger["spent_usd"] = projected
                if stage_name == STAGES[-1]:
                    ledger["status"] = "awaiting_final_owner_release"
                else:
                    ledger["status"] = "running"
            except Exception as exc:
                stage["status"] = StageStatus.FAILED.value
                stage["detail"] = f"{type(exc).__name__}: {exc}"
                ledger["status"] = "retryable" if int(stage["attempts"]) < 3 else "blocked"
            ledger["updated_at"] = _now()
            self.store.write(ledger)
            return ledger

    def _verified_decision(self) -> dict[str, object]:
        decision = _read_object(self.store.studio / "OWNER-DECISION.json")
        digest = str(decision.get("decision_hash", ""))
        unsigned = dict(decision)
        unsigned.pop("decision_hash", None)
        if not digest or _hash(unsigned) != digest:
            raise StudioApprovalError("owner decision integrity check failed")
        required = ("owner_approved", "paid_execution_enabled", "external_execution_enabled")
        if any(decision.get(name) is not True for name in required):
            raise StudioExecutionError("owner decision does not authorize execution")
        if decision.get("publishing_enabled") is not False:
            raise StudioExecutionError("publishing must remain disabled during production")
        return decision

    def _verify_ledger_binding(self, ledger: Mapping[str, object]) -> None:
        decision = self._verified_decision()
        if ledger.get("decision_hash") != decision.get("decision_hash"):
            raise StudioExecutionError("ledger is not bound to the current owner decision")
        if ledger.get("preflight_sha256") != _sha(self.store.studio / "EXECUTION-PREFLIGHT.json"):
            raise StudioExecutionError("execution preflight changed after initialization")

    def _verify_artifacts(self, artifacts: tuple[str, ...]) -> list[dict[str, object]]:
        if not artifacts:
            raise StudioExecutionError("stage produced no evidence artifacts")
        root = self.store.studio
        evidence: list[dict[str, object]] = []
        for value in artifacts:
            path = (root / value).resolve()
            try:
                relative = path.relative_to(root)
            except ValueError as exc:
                raise StudioExecutionError("stage artifact escaped studio directory") from exc
            if not path.is_file():
                raise StudioExecutionError(f"stage artifact is missing: {relative}")
            evidence.append({"path": relative.as_posix(), "sha256": _sha(path),
                             "size_bytes": path.stat().st_size})
        return evidence


def execution_status(studio_directory: str | Path) -> dict[str, object]:
    store = StudioExecutionStore(studio_directory)
    return store.read() or {"status": "not_initialized", "stages": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or run owner-approved studio execution")
    parser.add_argument("--studio-dir", required=True)
    parser.add_argument("command", choices=("status", "provider-status", "initialize", "run-next"))
    args = parser.parse_args()
    if args.command == "status":
        result = execution_status(args.studio_dir)
    elif args.command == "provider-status":
        from .studio_provider_handlers import ProductionProviderConfig
        result = ProductionProviderConfig.from_environment().status()
    else:
        if args.command == "initialize":
            # Initialization performs validation and reservation only.
            result = StudioExecutor(args.studio_dir, {}).initialize()
        else:
            from .studio_provider_handlers import (
                ProductionProviderConfig,
                build_production_handlers,
            )
            config = ProductionProviderConfig.from_environment()
            handlers, estimates = build_production_handlers(config)
            executor = StudioExecutor(args.studio_dir, handlers,
                                      stage_cost_estimates=estimates)
            if executor.store.read() is None:
                executor.initialize()
            result = executor.run_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
