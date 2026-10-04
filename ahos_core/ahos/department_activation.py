"""Activate department preparation without altering coding jobs or approving spend."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .department_structure import CORE_DEPARTMENTS
from .department_context import grounded_objective

DEPARTMENT_OBJECTIVES = {
    "software": "Audit the supplied AHOS requirements and prepare an implementation backlog with acceptance criteria, dependencies and tests. Treat coding work as pending until verified changes exist.",
    "quality": "Prepare acceptance checks for autonomous coding and cartoon episodes: regressions, character identity, age-appropriate voices, continuity and audiovisual quality. Provide observable pass criteria, not claimed results.",
    "research": "Prepare a research backlog for improving AHOS with free tools: evaluation questions, source verification requirements, license checks and integration experiments. Clearly label unverified recommendations; no claim of live research.",
    "infrastructure": "Prepare an operations runbook for Windows continuous service: restart recovery, health, logging, backup, dependency checks and provider outages. No claim of installed infrastructure.",
    "data": "Define traceable character, episode, voice, task and production evidence schemas, retention and consistency checks. Distinguish existing supplied evidence from proposed data.",
    "creative": "Prepare a professional 8-minute preschool cartoon concept and storyboard brief using only approved character facts provided. If cast data is missing list it as a blocker; do not invent canonical ages or voices.",
    "marketing": "Prepare an audience and channel strategy for the multilingual cartoon series, content calendar and measurable experiments. Label market assumptions; no publishing or advertising purchases.",
    "sales": "Prepare a monetization and partnership offer draft for the cartoon studio with qualification questions and proposed packages. No customer contact or asserted revenue.",
    "finance": "Prepare a production cost model separating known prices from unknown inputs, zero-cost planning versus paid rendering, budget ceilings and owner approvals. Do not invent actual provider prices.",
    "operations": "Prepare the operating workflow from request through departments, dependency handoffs, quality checks and final owner approval. Include exception handling and responsibilities.",
    "support": "Prepare a support knowledge base for task status, missing credentials, provider timeouts, approval and episode review, plus escalation criteria. Do not expose credentials.",
}


def activate_departments(runtime_dir: Path, *, allow_external: bool, model: str = "openrouter/free", max_workers: int = 3) -> dict[str, object]:
    from .department_provider import DepartmentProviderConfig
    from .department_runtime import DepartmentRuntime, DepartmentTask
    if not allow_external:
        raise ValueError("external AI generation requires --allow-external")
    DepartmentProviderConfig(allow_external=True, model_id=model)
    if not 1 <= max_workers <= 8:
        raise ValueError("parallel workers must be between 1 and 8")
    runtime_dir = Path(runtime_dir).resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path = runtime_dir / "company-service-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError("company config must be an object")
    department_runtime = DepartmentRuntime(runtime_dir / "departments", generator=None, max_workers=max_workers)
    department_runtime.supersede_bootstrap()
    existing = {item["task_id"] for item in department_runtime.snapshot()["tasks"]}
    dependencies = {"quality": ("software", "data", "creative"), "marketing": ("creative", "research"), "sales": ("marketing", "finance"), "operations": ("infrastructure", "finance", "support")}
    order = ("software", "research", "infrastructure", "data", "creative", "finance", "support", "quality", "marketing", "sales", "operations")
    for department in order:
        task_id = "DEPT-GROUNDED-" + department
        if task_id not in existing:
            department_runtime.enqueue(DepartmentTask(task_id, department, grounded_objective(DEPARTMENT_OBJECTIVES[department]), dependencies=tuple("DEPT-GROUNDED-" + d for d in dependencies.get(department, ()))))
    config["departments"] = {"enabled": True, "allow_external": True, "model": model, "max_workers": max_workers}
    temporary = config_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(config_path)
    return {"departments": len(CORE_DEPARTMENTS), "config": str(config_path), "status": "queued", "paid_execution_enabled": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--allow-external", action="store_true")
    parser.add_argument("--model", default="openrouter/free")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--retry-failed-provider", action="store_true")
    parser.add_argument("--enable-brain", action="store_true",
                        help="Enable local gap observation, repair dispatch and daily GitHub metadata checks")
    args = parser.parse_args()
    print(json.dumps(activate_departments(Path(args.runtime_dir), allow_external=args.allow_external, model=args.model, max_workers=args.max_workers)))
    if args.enable_brain:
        config_path = Path(args.runtime_dir) / "company-service-config.json"
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        config["holding_brain"] = {"enabled": True, "dispatch": True,
                                   "interval_seconds": 300, "watch_upstream": True,
                                   "allow_external": args.allow_external}
        temp = config_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(config_path)
    if args.retry_failed_provider:
        from .department_runtime import DepartmentRuntime
        print(json.dumps({"provider_tasks_requeued": DepartmentRuntime(Path(args.runtime_dir) / "departments").retry_failed_providers()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
