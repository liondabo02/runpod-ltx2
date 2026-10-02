from __future__ import annotations

import hashlib
import argparse
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .coding_supervisor import CodingSupervisorStore, CodingTaskRecord
from .coding_worker import CodingBacklogItem
from .work_order import WorkOrder, WorkOrderStatus, WorkOrderStore


class CodingBridgeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CodingWorkContract:
    work_order_id: str
    title: str
    repository: Path
    base_ref: str
    allowed_paths: tuple[str, ...]
    test_commands: tuple[tuple[str, ...], ...]
    max_attempts: int = 2

    @classmethod
    def from_json(cls, path: str | Path) -> "CodingWorkContract":
        source = Path(path)
        raw = json.loads(source.read_text(encoding="utf-8"))
        if raw.get("schema") != "ahos.coding-work-contract.v1":
            raise CodingBridgeError("unsupported coding work contract schema")
        allowed = tuple(str(item) for item in raw.get("allowed_paths", ()))
        tests = tuple(tuple(str(part) for part in command) for command in raw.get("test_commands", ()))
        contract = cls(
            work_order_id=str(raw.get("work_order_id", "")).strip(),
            title=str(raw.get("title", "")).strip(),
            repository=Path(str(raw.get("repository", ""))).resolve(),
            base_ref=str(raw.get("base_ref", "HEAD")).strip(),
            allowed_paths=allowed,
            test_commands=tests,
            max_attempts=int(raw.get("max_attempts", 2)),
        )
        contract.validate()
        return contract

    def validate(self) -> None:
        if not self.work_order_id or not self.title:
            raise CodingBridgeError("work_order_id and title are required")
        if not (self.repository / ".git").exists() and not (self.repository / ".git").is_file():
            raise CodingBridgeError("repository must be an existing Git worktree")
        if not self.allowed_paths:
            raise CodingBridgeError("allowed_paths must not be empty")
        for value in self.allowed_paths:
            normalized = PurePosixPath(value.replace("\\", "/"))
            if normalized.is_absolute() or ".." in normalized.parts:
                raise CodingBridgeError(f"unsafe allowed path: {value}")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise CodingBridgeError("max_attempts must be between 1 and 5")

    def fingerprint(self) -> str:
        payload = {
            "work_order_id": self.work_order_id,
            "title": self.title,
            "repository": str(self.repository),
            "base_ref": self.base_ref,
            "allowed_paths": self.allowed_paths,
            "test_commands": self.test_commands,
            "max_attempts": self.max_attempts,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class WorkOrderCodingBridge:
    """Translate an explicitly scoped READY software order into one coding task."""

    def __init__(self, work_orders: WorkOrderStore, coding: CodingSupervisorStore) -> None:
        self.work_orders = work_orders
        self.coding = coding

    def dispatch(self, contract: CodingWorkContract) -> CodingTaskRecord:
        contract.validate()
        order = self.work_orders.get(contract.work_order_id)
        self._require_dispatchable(order)
        assert order is not None
        item = CodingBacklogItem(
            task_id=f"coding-{order.work_order_id}",
            title=contract.title,
            repository=contract.repository,
            base_ref=contract.base_ref,
            allowed_paths=contract.allowed_paths,
            test_commands=contract.test_commands,
        )
        record = self.coding.enqueue(
            item,
            idempotency_key=f"work-order:{order.work_order_id}:{contract.fingerprint()}",
            max_attempts=contract.max_attempts,
            priority=order.priority,
        )
        if order.status is WorkOrderStatus.READY:
            self.work_orders.transition(order.work_order_id, WorkOrderStatus.IN_PROGRESS)
        return record

    @staticmethod
    def _require_dispatchable(order: WorkOrder | None) -> None:
        if order is None:
            raise CodingBridgeError("unknown work order")
        if order.status not in {WorkOrderStatus.READY, WorkOrderStatus.IN_PROGRESS}:
            raise CodingBridgeError("work order must be READY")
        if order.routing_department != "software":
            raise CodingBridgeError("only software work orders may enter the coding queue")
        required = set(order.capability_requirements)
        if not required.intersection({"coding", "software_engineering", "automation"}):
            raise CodingBridgeError("work order has no coding capability requirement")


def dispatch_contract_directory(
    work_order_file: str | Path,
    coding_queue_file: str | Path,
    contracts_directory: str | Path,
) -> tuple[CodingTaskRecord, ...]:
    bridge = WorkOrderCodingBridge(
        WorkOrderStore(work_order_file), CodingSupervisorStore(coding_queue_file)
    )
    dispatched: list[CodingTaskRecord] = []
    for path in sorted(Path(contracts_directory).glob("*.json")):
        dispatched.append(bridge.dispatch(CodingWorkContract.from_json(path)))
    return tuple(dispatched)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch scoped software work orders")
    parser.add_argument("--work-orders", required=True)
    parser.add_argument("--coding-queue", required=True)
    parser.add_argument("--contracts-dir", required=True)
    args = parser.parse_args()
    records = dispatch_contract_directory(
        args.work_orders, args.coding_queue, args.contracts_dir
    )
    print(json.dumps({"dispatched": [item.task_id for item in records]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
