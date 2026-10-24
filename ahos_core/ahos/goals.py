"""Goal continuation: broad objectives are carried step by step to the end.

A request like "stüdyoyu geliştir" is not one mission. It becomes a **goal**
with ordered steps; each daemon turn executes exactly one pending step, records
its evidence and moves on. The goal is finished only when every step is done; a
step that fails twice is marked blocked and the goal continues with the next
step instead of stalling the whole loop.

Storage is append-friendly: ``runtime/goals/<id>.json`` plus ``goals-log.jsonl``.
Nothing is deleted — steps keep their history.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

STEP_TEMPLATE = (
    ("analiz", "mevcut durumu analiz et ve eksikleri listele"),
    ("uygulama-1", "ilk somut iyileştirmeyi uygula ve doğrula"),
    ("uygulama-2", "ikinci iyileştirmeyi uygula ve doğrula"),
    ("kapi", "kabul testlerini çalıştır, düşenleri düzelt"),
    ("belge", "yapılanları kısa bir belgeyle kaydet"),
)
MAX_ATTEMPTS = 2


@dataclass
class Step:
    step_id: str
    title: str
    status: str = "pending"
    attempts: int = 0
    note: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "status": self.status,
            "attempts": self.attempts,
            "note": self.note,
            "updated_at": self.updated_at,
        }


@dataclass
class Goal:
    goal_id: str
    title: str
    department_id: str
    steps: list[Step] = field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "department_id": self.department_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [step.to_dict() for step in self.steps],
        }

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for step in self.steps if step.status == "done")
        return round(done / len(self.steps), 3)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _dir(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "goals"


def _path(runtime_dir: str | Path, goal_id: str) -> Path:
    return _dir(runtime_dir) / f"{goal_id}.json"


def _goal_id(title: str, department_id: str) -> str:
    digest = hashlib.sha256(f"{department_id}|{title.casefold()}".encode("utf-8")).hexdigest()[:12]
    return f"G-{digest}"


def _steps_for(title: str) -> list[Step]:
    subject = re.sub(r"\s+", " ", title).strip()
    return [
        Step(step_id=step_id, title=f"{subject} · {wording}")
        for step_id, wording in STEP_TEMPLATE
    ]


def create(
    runtime_dir: str | Path,
    title: str,
    department_id: str,
    *,
    steps: list[str] | None = None,
) -> Goal:
    runtime = Path(runtime_dir)
    _dir(runtime).mkdir(parents=True, exist_ok=True)
    goal_id = _goal_id(title, department_id)
    existing = load(runtime, goal_id)
    if existing is not None:
        return existing
    goal = Goal(
        goal_id=goal_id,
        title=title.strip(),
        department_id=department_id,
        steps=[Step(step_id=f"s{i+1}", title=text) for i, text in enumerate(steps)]
        if steps
        else _steps_for(title),
        created_at=_now(),
        updated_at=_now(),
    )
    save(runtime, goal)
    _log(runtime, {"event": "created", "goal_id": goal_id, "title": goal.title})
    return goal


def save(runtime_dir: str | Path, goal: Goal) -> Path:
    runtime = Path(runtime_dir)
    path = _path(runtime, goal.goal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    goal.updated_at = _now()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(goal.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def load(runtime_dir: str | Path, goal_id: str) -> Goal | None:
    path = _path(runtime_dir, goal_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    steps = [
        Step(
            step_id=str(item.get("step_id") or ""),
            title=str(item.get("title") or ""),
            status=str(item.get("status") or "pending"),
            attempts=int(item.get("attempts") or 0),
            note=str(item.get("note") or ""),
            updated_at=str(item.get("updated_at") or ""),
        )
        for item in payload.get("steps") or []
        if isinstance(item, dict)
    ]
    return Goal(
        goal_id=str(payload.get("goal_id") or goal_id),
        title=str(payload.get("title") or ""),
        department_id=str(payload.get("department_id") or ""),
        steps=steps,
        status=str(payload.get("status") or "active"),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
    )


def all_goals(runtime_dir: str | Path) -> list[Goal]:
    folder = _dir(runtime_dir)
    goals: list[Goal] = []
    if not folder.is_dir():
        return goals
    for path in sorted(folder.glob("*.json")):
        goal = load(runtime_dir, path.stem)
        if goal is not None:
            goals.append(goal)
    return goals


def next_step(runtime_dir: str | Path, excluded: set[str] | None = None) -> tuple[Goal, Step] | None:
    """Oldest active goal's first pending (or retryable) step."""

    excluded = excluded or set()
    for goal in all_goals(runtime_dir):
        if goal.status != "active" or goal.department_id in excluded:
            continue
        for step in goal.steps:
            if step.status == "pending":
                return goal, step
    return None


def advance(
    runtime_dir: str | Path,
    goal_id: str,
    step_id: str,
    *,
    success: bool,
    note: str = "",
) -> Goal | None:
    goal = load(runtime_dir, goal_id)
    if goal is None:
        return None
    for step in goal.steps:
        if step.step_id != step_id:
            continue
        step.updated_at = _now()
        step.note = note[:300]
        if success:
            step.status = "done"
        else:
            step.attempts += 1
            step.status = "blocked" if step.attempts >= MAX_ATTEMPTS else "pending"
        break
    if all(step.status in {"done", "blocked"} for step in goal.steps):
        goal.status = "done" if all(step.status == "done" for step in goal.steps) else "blocked"
    save(runtime_dir, goal)
    _log(
        runtime_dir,
        {
            "event": "step",
            "goal_id": goal_id,
            "step_id": step_id,
            "success": success,
            "note": note[:200],
            "progress": goal.progress,
        },
    )
    return goal


def _log(runtime_dir: str | Path, row: dict) -> None:
    path = Path(runtime_dir) / "goals-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": _now(), **row}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def progress(runtime_dir: str | Path) -> list[dict]:
    return [
        {
            "goal_id": goal.goal_id,
            "title": goal.title,
            "department": goal.department_id,
            "status": goal.status,
            "progress": goal.progress,
            "steps": [
                {"title": step.title, "status": step.status, "attempts": step.attempts}
                for step in goal.steps
            ],
        }
        for goal in all_goals(runtime_dir)
    ]


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    if args and not args[0].startswith("--"):
        from .owner_console import build_default_console

        text = " ".join(arg for arg in args if not arg.startswith("--") and arg != str(runtime))
        console = build_default_console(runtime)
        spec, _score = console.route(text)
        department = spec.department_id if spec is not None else "genel"
        goal = create(runtime, text, department)
        print(f"hedef: {goal.goal_id} · {goal.title} · {len(goal.steps)} adım")
        return 0
    for item in progress(runtime):
        print(f"{item['goal_id']} %{round(item['progress']*100)} {item['status']} · {item['title'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
