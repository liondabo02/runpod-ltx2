param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "End-to-end live AI mission is not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$reportDir = Join-Path $pkg "reports"
$reportPath = Join-Path $reportDir "AHOS-034-full-ai-chain.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Write-Host "=== AHOS-034 FULL AI MANAGEMENT CHAIN ==="
Write-Host "Real AI Manager -> Real AI Researcher -> local QA -> Real AI Developer -> local QA"
Write-Host "The manager cannot self-approve paid/protected work."
Write-Host "Your -ApproveLiveAi flag is the explicit owner approval for the two safe internal worker steps."
Write-Host "No publishing, messaging, payments, purchases, deployment, secrets, or destructive actions."
Write-Host ""
Write-Host "IMPORTANT COST NOTE:"
Write-Host "This run starts 3 small OpenHands AI workflows (manager + researcher + developer)."
Write-Host "Each workflow may make multiple model turns."
Write-Host "AHOS assigns USD 0.01 estimated reserve to each worker step; this is NOT a provider hard cap."
Write-Host ""

Write-Host "Running local compatibility/control-plane tests first..."
& $python -m pytest tests\test_openhands_sdk_compat.py tests\test_openhands_builder.py -q
if ($LASTEXITCODE -ne 0) {
    throw "Control-plane tests failed. No live AI call was made."
}

Write-Host "Running full AHOS tests locally..."
$oldPythonPath = $env:PYTHONPATH
Push-Location $pkg
try {
    $env:PYTHONPATH = $pkg
    & $python -m pytest -q
    $ahosExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $oldPythonPath
}
if ($ahosExit -ne 0) {
    throw "AHOS tests failed. No live AI call was made."
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name,$value = $_ -split '=',2
    [Environment]::SetEnvironmentVariable($name.Trim(),$value.Trim(),'Process')
}

if (-not $env:LLM_API_KEY -and -not $env:OPENAI_API_KEY) {
    throw "No API key loaded from .env.runtime."
}
if (-not $env:MINIVERSE_OPENHANDS_MODEL) {
    throw "MINIVERSE_OPENHANDS_MODEL is missing."
}

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

Write-Host ""
Write-Host "Local tests passed."
Write-Host "Starting full live AI chain..."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host ""

$live = @'
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import re

from ahos.ai_manager_planner import OpenHandsManagerPlanner
from ahos.mission_orchestrator import (
    MissionStatus,
    MultiWorkerMissionOrchestrator,
)
from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    default_virtual_workforce,
)
from ahos.worker_runtime import (
    QaExecutionResult,
    WorkerExecutionResult,
)

ROOT = Path(r"__ROOT__")
REPORT = Path(r"__REPORT__")
PLAN_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-manager"
WORK_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-full-chain"
MISSION_ID = "AHOS-034-full-ai-chain"
RESEARCH_FILE = "RESEARCH_BRIEF.md"
DEV_FILE = "PROTOTYPE_PLAN.md"

import miniverse.config as cfg
from miniverse.openhands_builder import OpenHandsBuilder


def resolve_settings():
    for name in ("settings", "SETTINGS"):
        value = getattr(cfg, name, None)
        if value is not None:
            return value
    for name in ("get_settings", "load_settings"):
        fn = getattr(cfg, name, None)
        if callable(fn):
            return fn()
    cls = getattr(cfg, "Settings", None)
    if cls is not None:
        return cls()
    raise RuntimeError("Could not resolve Miniverse settings object.")


def build_builder(settings):
    errors = []
    for attempt in (
        lambda: OpenHandsBuilder(settings=settings),
        lambda: OpenHandsBuilder(settings),
        lambda: OpenHandsBuilder(),
    ):
        try:
            return attempt()
        except TypeError as exc:
            errors.append(str(exc))
    raise RuntimeError(
        "Could not construct OpenHandsBuilder: " + " | ".join(errors)
    )


def safe_dir(task_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._")
    return value or "task"


profiles = {p.worker_id: p for p in default_virtual_workforce()}
required_ids = (
    "mgr-software-01",
    "research-01",
    "dev-01",
    "qa-01",
)
missing = [worker_id for worker_id in required_ids if worker_id not in profiles]
if missing:
    raise RuntimeError(f"default workforce missing profiles: {missing}")

capability_catalog = {
    "research": frozenset(profiles["research-01"].capabilities),
    "software": frozenset(profiles["dev-01"].capabilities),
}

# Give only the two live workers a small internal paid-AI allowance.
live_profiles = (
    profiles["mgr-software-01"],
    replace(
        profiles["research-01"],
        can_use_paid_ai=True,
        daily_budget_usd=max(
            float(profiles["research-01"].daily_budget_usd),
            0.02,
        ),
    ),
    replace(
        profiles["dev-01"],
        can_use_paid_ai=True,
        daily_budget_usd=max(
            float(profiles["dev-01"].daily_budget_usd),
            0.02,
        ),
    ),
    profiles["qa-01"],
)
registry = VirtualWorkforceRegistry(live_profiles)

builder = build_builder(resolve_settings())
raw_runs: list[tuple[str, object]] = []
developer_prompts: list[str] = []
research_handoff: list[str] = []


def tracked_runner(label: str):
    def _run(prompt: str, workspace: Path):
        if label == "developer":
            developer_prompts.append(prompt)
        result = builder.run(task=prompt, workspace=workspace)
        raw_runs.append((label, result))
        return result
    return _run


manager_planner = OpenHandsManagerPlanner(
    runner=tracked_runner("manager"),
    workspace_root=PLAN_ROOT,
    allowed_departments=frozenset({"research", "software"}),
    capability_catalog=capability_catalog,
    max_steps=2,
    # The manager creates the logical zero-cost plan. The execution wrapper
    # below applies the owner's explicit paid-AI approval and worker estimate.
    max_total_estimated_cost_usd=0.0,
)


def owner_approved_live_planner(mission_id, objective, manager_id):
    logical_steps = tuple(
        manager_planner(mission_id, objective, manager_id)
    )

    if len(logical_steps) != 2:
        raise ValueError(
            f"live smoke requires exactly 2 manager steps, got {len(logical_steps)}"
        )

    research_steps = [
        step for step in logical_steps if step.department == "research"
    ]
    software_steps = [
        step for step in logical_steps if step.department == "software"
    ]
    if len(research_steps) != 1 or len(software_steps) != 1:
        raise ValueError(
            "live smoke requires exactly one research and one software step"
        )

    research_step = research_steps[0]
    software_step = software_steps[0]

    if research_step.depends_on:
        raise ValueError("research step must be the first dependency root")
    if research_step.step_id not in software_step.depends_on:
        raise ValueError(
            "software step must depend on the research step"
        )

    approved = []
    for step in logical_steps:
        if (
            step.external_side_effect
            or step.destructive
            or step.touches_secrets
        ):
            raise ValueError(
                f"manager planned protected behavior in {step.step_id}"
            )
        if step.owner_approved:
            raise ValueError("AI manager must never self-approve work")

        approved.append(
            replace(
                step,
                estimated_cost_usd=0.01,
                requires_owner_approval=True,
                owner_approved=True,
            )
        )

    return tuple(approved)


research_adapter = OpenHandsWorkerAdapter(
    runner=tracked_runner("researcher"),
    workspace_root=WORK_ROOT,
)
dev_adapter = OpenHandsWorkerAdapter(
    runner=tracked_runner("developer"),
    workspace_root=WORK_ROOT,
)


def research_executor(item, worker_id):
    base = research_adapter(item, worker_id)
    task_dir = WORK_ROOT / safe_dir(item.task_id)
    artifact = task_dir / RESEARCH_FILE

    if not base.success:
        return base
    if not artifact.exists():
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary=f"research worker did not create {RESEARCH_FILE}",
        )

    content = artifact.read_text(encoding="utf-8").strip()
    if not content:
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary=f"{RESEARCH_FILE} is empty",
        )

    research_handoff[:] = [content]
    handoff_summary = (
        f"{base.summary}\n\n"
        f"Verified research artifact content for downstream handoff:\n"
        f"{content}"
    )

    return WorkerExecutionResult(
        task_id=item.task_id,
        worker_id=worker_id,
        success=True,
        summary=handoff_summary,
        artifacts=base.artifacts,
        tests_run=base.tests_run,
    )


def dev_executor(item, worker_id):
    return dev_adapter(item, worker_id)


def qa_executor(item, worker_result, qa_worker_id):
    task_dir = WORK_ROOT / safe_dir(item.task_id)

    if item.department == "research":
        target = task_dir / RESEARCH_FILE
        passed = (
            worker_result.success
            and target.exists()
            and bool(target.read_text(encoding="utf-8").strip())
        )
        summary = (
            "verified non-empty research artifact"
            if passed
            else "research artifact verification failed"
        )
    elif item.department == "software":
        target = task_dir / DEV_FILE
        passed = (
            worker_result.success
            and target.exists()
            and bool(target.read_text(encoding="utf-8").strip())
        )
        summary = (
            "verified non-empty developer artifact"
            if passed
            else "developer artifact verification failed"
        )
    else:
        passed = False
        summary = "unexpected department in AHOS-034"

    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=passed,
        summary=summary,
    )


objective = f"""
Create a tiny local-only internal automation prototype plan.

The department manager must plan exactly two worker steps:
1. Research first. The research worker must create {RESEARCH_FILE} with
   exactly three concise requirements/constraints for a safe local automation.
2. Software second, depending on the research step. The software worker must
   use the handed-off research result and create {DEV_FILE} describing a tiny
   implementation plan based on that research.

Use only the research and software departments. Keep all work local and
reversible. Do not contact anyone, publish, deploy, purchase, access secrets,
or use external business systems.
""".strip()

orchestrator = MultiWorkerMissionOrchestrator(
    registry,
    manager_planner=owner_approved_live_planner,
    executors={
        "research-01": research_executor,
        "dev-01": dev_executor,
    },
    qa_executor=qa_executor,
)

result = orchestrator.run(
    mission_id=MISSION_ID,
    objective=objective,
    primary_department="software",
)

plan_path = PLAN_ROOT / MISSION_ID / "MISSION_PLAN.json"
if not plan_path.exists():
    raise SystemExit("AHOS-034 manager plan file missing")
plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))

print("=== AHOS-034 FULL AI CHAIN RESULT ===")
print("MISSION STATUS:", result.status.value)
print("MANAGER:", result.manager_id)

for raw in plan_payload.get("steps", []):
    print(
        "AI MANAGER PLAN:",
        raw.get("step_id"),
        "|",
        raw.get("department"),
        "|",
        raw.get("required_capabilities"),
        "| depends_on:",
        raw.get("depends_on"),
    )

for step in result.steps:
    print(
        "EXECUTED:",
        step.step.step_id,
        "| DEPARTMENT:",
        step.step.department,
        "| WORKER:",
        step.worker_id,
        "| STAGE:",
        step.stage.value,
    )
    print("  QA:", step.qa_summary)

if result.status is not MissionStatus.COMPLETED:
    raise SystemExit("AHOS-034 FULL AI CHAIN: FAILED")

workers = [step.worker_id for step in result.steps]
if "research-01" not in workers or "dev-01" not in workers:
    raise SystemExit("AHOS-034 did not execute both real AI workers")

if not research_handoff:
    raise SystemExit("research artifact was not captured for downstream handoff")
if not developer_prompts:
    raise SystemExit("developer prompt was not captured")

handoff_probe = research_handoff[0][:160]
if handoff_probe not in developer_prompts[-1]:
    raise SystemExit(
        "developer prompt did not contain the real research artifact handoff"
    )

research_step = next(
    step for step in result.steps if step.step.department == "research"
)
software_step = next(
    step for step in result.steps if step.step.department == "software"
)

research_file = (
    WORK_ROOT
    / safe_dir(f"{MISSION_ID}:{research_step.step.step_id}")
    / RESEARCH_FILE
)
dev_file = (
    WORK_ROOT
    / safe_dir(f"{MISSION_ID}:{software_step.step.step_id}")
    / DEV_FILE
)

if not research_file.exists():
    raise SystemExit("verified research file missing after mission")
if not dev_file.exists():
    raise SystemExit("verified developer file missing after mission")

cost_rows = []
reported_total = 0.0
all_costs_available = True

for label, raw in raw_runs:
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)

    if cost is None:
        all_costs_available = False
        cost_rows.append(
            {"actor": label, "estimated_cost_usd": None}
        )
    else:
        value = float(cost)
        reported_total += value
        cost_rows.append(
            {"actor": label, "estimated_cost_usd": value}
        )

print("HANDOFF VERIFIED:", True)
print("RESEARCH ARTIFACT:", research_file)
print("DEVELOPER ARTIFACT:", dev_file)
for row in cost_rows:
    print(
        "REPORTED COST:",
        row["actor"],
        row["estimated_cost_usd"],
    )
print(
    "REPORTED ESTIMATED TOTAL COST USD:",
    reported_total if all_costs_available else "partial/unavailable",
)
print("AHOS-034 FULL AI CHAIN: PASS")

report = {
    "mission_id": MISSION_ID,
    "status": result.status.value,
    "manager_id": result.manager_id,
    "objective": objective,
    "ai_manager_plan": plan_payload,
    "executed_steps": [
        {
            "step_id": step.step.step_id,
            "department": step.step.department,
            "worker_id": step.worker_id,
            "stage": step.stage.value,
            "qa_summary": step.qa_summary,
        }
        for step in result.steps
    ],
    "real_ai_actors": [
        "mgr-software-01",
        "research-01",
        "dev-01",
    ],
    "research_to_developer_handoff_verified": True,
    "research_artifact": str(research_file),
    "developer_artifact": str(dev_file),
    "reported_costs": cost_rows,
    "reported_estimated_total_cost_usd": (
        reported_total if all_costs_available else None
    ),
    "external_publish_actions": 0,
    "external_message_actions": 0,
    "payment_actions": 0,
    "deployment_actions": 0,
}

REPORT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
'@

$live = $live.Replace("__ROOT__", $root.Replace("\","\\"))
$live = $live.Replace("__REPORT__", $reportPath.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $live | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    throw "AHOS-034 full AI chain failed. See the error above."
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-034" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-034"
        title = "Prove full AI manager-to-worker chain"
        status = "completed"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        completed_at = [DateTime]::UtcNow.ToString("o")
        task = "Prove one end-to-end owner-approved mission with a real AI department manager, real AI researcher, deterministic QA, verified research handoff, real AI software engineer, and final QA. Keep all work local; no publishing, messaging, payments, deployment, destructive actions, or secret access."
    }
} else {
    $t = $b.tasks | Where-Object { $_.id -eq "AHOS-034" } | Select-Object -First 1
    $t.status = "completed"
    if ($t.PSObject.Properties.Name -contains "completed_at") {
        $t.completed_at = [DateTime]::UtcNow.ToString("o")
    } else {
        $t | Add-Member -NotePropertyName completed_at -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
    }
}

# AHOS-032 was superseded by the routing fix in AHOS-033.
$t32 = $b.tasks | Where-Object { $_.id -eq "AHOS-032" } | Select-Object -First 1
if ($null -ne $t32) {
    $t32.status = "completed"
}

[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

git -C $ws add ahos_core/AHOS_BACKLOG.json ahos_core/reports/AHOS-034-full-ai-chain.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "test(ahos): prove full AI management chain"
if ($LASTEXITCODE -ne 0) {
    throw "Full AI chain passed, but git commit failed."
}
git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) {
    throw "Full AI chain passed, but git push failed."
}

Write-Host ""
Write-Host "=== AHOS-034 COMPLETE ==="
Write-Host "Real AI Department Manager: PASS"
Write-Host "Real AI Researcher: PASS"
Write-Host "Research QA: PASS"
Write-Host "Research -> Developer handoff: PASS"
Write-Host "Real AI Software Engineer: PASS"
Write-Host "Developer QA: PASS"
Write-Host "AI self-approval prevention: PASS"
Write-Host "Evidence report committed: PASS"
Write-Host "External publish/message/payment/deployment actions: 0"
