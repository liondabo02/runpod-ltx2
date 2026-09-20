from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BACKLOG_PATH = Path(__file__).resolve().parent.parent / "AHOS_BACKLOG.json"

ALLOWED_STATUSES = frozenset({"planned", "in_progress", "blocked", "completed"})
ALLOWED_AUTHORITIES = frozenset({"A", "B", "C", "D"})
ALLOWED_RISKS = frozenset({"low", "medium", "high"})
OWNER_APPROVAL_AUTHORITIES = frozenset({"C", "D"})
REQUIRED_TOP_LEVEL_FIELDS = ("version", "project", "rules", "tasks")
REQUIRED_RULE_FIELDS = (
    "autonomous_authority",
    "never_auto_merge_main",
    "owner_approval_required",
)
REQUIRED_TASK_FIELDS = (
    "id",
    "title",
    "task",
    "status",
    "authority",
    "risk",
    "requires_owner_approval",
)


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_backlog(data: object) -> ValidationResult:
    """Validate an AHOS backlog without changing the supplied value."""
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ValidationResult(("backlog must be a JSON object",))

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            errors.append(f"missing top-level field: {field}")

    if not isinstance(data.get("version"), int) or isinstance(data.get("version"), bool):
        errors.append("top-level version must be an integer")
    if not isinstance(data.get("project"), str) or not data.get("project", "").strip():
        errors.append("top-level project must be a non-empty string")

    rules = data.get("rules")
    if not isinstance(rules, Mapping):
        errors.append("top-level rules must be an object")
    else:
        for field in REQUIRED_RULE_FIELDS:
            if field not in rules:
                errors.append(f"missing top-level rule: rules.{field}")

        autonomous_authority = rules.get("autonomous_authority")
        if autonomous_authority != ["A", "B"]:
            errors.append("rules.autonomous_authority must be exactly ['A', 'B']")

        if rules.get("never_auto_merge_main") is not True:
            errors.append("rules.never_auto_merge_main must be true")

        owner_approval_required = rules.get("owner_approval_required")
        if owner_approval_required != ["C", "D"]:
            errors.append("rules.owner_approval_required must be exactly ['C', 'D']")

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        errors.append("top-level tasks must be an array")
        return ValidationResult(tuple(errors))

    seen_ids: set[str] = set()
    for index, task in enumerate(tasks):
        prefix = f"tasks[{index}]"
        if not isinstance(task, Mapping):
            errors.append(f"{prefix} must be an object")
            continue

        for field in REQUIRED_TASK_FIELDS:
            if field not in task:
                errors.append(f"{prefix} missing field: {field}")

        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif task_id in seen_ids:
            errors.append(f"duplicate task id: {task_id}")
        else:
            seen_ids.add(task_id)

        for field in ("title", "task"):
            value = task.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")

        status = task.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(ALLOWED_STATUSES)}")

        authority = task.get("authority")
        if authority not in ALLOWED_AUTHORITIES:
            errors.append(f"{prefix}.authority must be one of {sorted(ALLOWED_AUTHORITIES)}")

        risk = task.get("risk")
        if risk not in ALLOWED_RISKS:
            errors.append(f"{prefix}.risk must be one of {sorted(ALLOWED_RISKS)}")

        requires_owner_approval = task.get("requires_owner_approval")
        if not isinstance(requires_owner_approval, bool):
            errors.append(f"{prefix}.requires_owner_approval must be boolean")
        elif authority in ALLOWED_AUTHORITIES:
            expected_approval = authority in OWNER_APPROVAL_AUTHORITIES
            if requires_owner_approval is not expected_approval:
                errors.append(
                    f"{prefix}.requires_owner_approval must be {expected_approval} "
                    f"for authority {authority}"
                )

        if status == "completed":
            completed_at = task.get("completed_at")
            if not isinstance(completed_at, str) or not completed_at.strip():
                errors.append(f"{prefix}.completed_at is required for completed tasks")

    return ValidationResult(tuple(errors))


def load_and_validate(path: Path) -> ValidationResult:
    """Load and validate one backlog file, reporting file errors deterministically."""
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return ValidationResult((f"unable to read {path}: {exc}",))
    except json.JSONDecodeError as exc:
        return ValidationResult((f"invalid JSON in {path}: line {exc.lineno} column {exc.colno}",))
    return validate_backlog(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a local AHOS backlog file")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_BACKLOG_PATH)
    args = parser.parse_args(argv)

    result = load_and_validate(args.path)
    if result.is_valid:
        print(f"VALID: {args.path} ({len(json.loads(args.path.read_text(encoding='utf-8'))['tasks'])} tasks)")
        return 0

    print(f"INVALID: {args.path}")
    for error in result.errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
