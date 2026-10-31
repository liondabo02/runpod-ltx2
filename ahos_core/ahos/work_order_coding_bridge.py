from __future__ import annotations

import hashlib
import argparse
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .coding_supervisor import CodingSupervisorStore, CodingTaskRecord, CodingTaskStatus
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
        if not isinstance(raw, dict):
            raise CodingBridgeError("coding work contract must be a JSON object")
        if not isinstance(raw.get("repository"), str) or not raw["repository"].strip():
            raise CodingBridgeError("repository must be explicitly provided")
        if raw.get("schema") != "ahos.coding-work-contract.v1":
            raise CodingBridgeError("unsupported coding work contract schema")
        allowed = tuple(str(item) for item in raw.get("allowed_paths", ()))
        tests = tuple(tuple(str(part) for part in command) for command in raw.get("test_commands", ()))
        contract = cls(
            work_order_id=str(raw.get("work_order_id", "")).strip(),
            title=str(raw.get("title", "")).strip(),
            repository=Path(raw["repository"]).resolve(),
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
        if not self.test_commands:
            raise CodingBridgeError("at least one acceptance test command is required")
        for command in self.test_commands:
            if not command or not all(part.strip() for part in command):
                raise CodingBridgeError("acceptance test commands must contain non-empty arguments")
        for value in self.allowed_paths:
            normalized = PurePosixPath(value.replace("\\", "/"))
            if not value.strip() or normalized == PurePosixPath(".") or normalized.is_absolute() or ".." in normalized.parts:
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
    def _verify_owner_approved_evidence(record: CodingTaskRecord) -> None:
        """Fail closed if approval evidence or the reviewed patch has changed."""
        if not (record.owner_decision_at and record.approval_file
                and record.patch_file and record.evidence_sha256):
            raise CodingBridgeError("owner approval evidence is incomplete")
        try:
            approval_path = Path(record.approval_file)
            patch_path = Path(record.patch_file)
            approval_bytes = approval_path.read_bytes()
            if hashlib.sha256(approval_bytes).hexdigest() != record.evidence_sha256:
                raise CodingBridgeError("owner approval evidence was modified")
            approval = json.loads(approval_bytes.decode("utf-8"))
            if not isinstance(approval, dict):
                raise CodingBridgeError("owner approval payload is invalid")
            if hashlib.sha256(patch_path.read_bytes()).hexdigest() != approval.get("patch_sha256"):
                raise CodingBridgeError("owner reviewed patch was modified")
        except (OSError, UnicodeError, ValueError) as exc:
            raise CodingBridgeError("owner approval evidence cannot be verified") from exc

    def reconcile(self) -> tuple[WorkOrder, ...]:
        """Update software work orders from terminal coding decisions.

        COMPLETED means an owner-reviewed local patch is ready for integration.
        It does not mean the patch was merged, deployed, or published.
        """
        changes: list[WorkOrder] = []
        for order in self.work_orders.all():
            if order.status is not WorkOrderStatus.IN_PROGRESS or order.routing_department != "software":
                continue
            record = self.coding.get(f"coding-{order.work_order_id}")
            if record is None:
                continue
            if not record.idempotency_key.startswith(f"work-order:{order.work_order_id}:"):
                raise CodingBridgeError("coding queue identity does not match work order")
            if record.status is CodingTaskStatus.OWNER_APPROVED:
                self._verify_owner_approved_evidence(record)
                changes.append(self.work_orders.transition(order.work_order_id, WorkOrderStatus.COMPLETED))
            elif record.status in (CodingTaskStatus.OWNER_REJECTED, CodingTaskStatus.RETRIES_EXHAUSTED):
                changes.append(self.work_orders.transition(order.work_order_id, WorkOrderStatus.FAILED))
            elif record.status is CodingTaskStatus.CANCELLED:
                changes.append(self.work_orders.transition(order.work_order_id, WorkOrderStatus.CANCELLED))
        return tuple(changes)

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
    parser.add_argument("--contracts-dir", help="Optional contract folder for new dispatches")
    parser.add_argument("--reconcile", action="store_true", help="Sync owner-reviewed coding outcomes")
    args = parser.parse_args()
    if not args.contracts_dir and not args.reconcile:
        parser.error("provide --contracts-dir and/or --reconcile")
    records = (dispatch_contract_directory(args.work_orders, args.coding_queue, args.contracts_dir)
               if args.contracts_dir else ())
    changed = (WorkOrderCodingBridge(WorkOrderStore(args.work_orders),
               CodingSupervisorStore(args.coding_queue)).reconcile() if args.reconcile else ())
    print(json.dumps({"dispatched": [item.task_id for item in records],
                      "reconciled": [{"work_order_id": item.work_order_id,
                                      "status": item.status.value} for item in changed]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
