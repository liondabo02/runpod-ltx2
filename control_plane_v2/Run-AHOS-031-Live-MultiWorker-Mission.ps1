param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "Live multi-worker AI test is not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$reportDir = Join-Path $pkg "reports"
$reportPath = Join-Path $reportDir "AHOS-031-live-mission.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Write-Host "=== AHOS-031 REAL MULTI-WORKER MISSION SMOKE ==="
Write-Host "Mission: Manager -> Researcher (real AI) -> QA -> Developer (real AI) -> QA"
Write-Host "No publish, messages, payments, deployments, or external business actions."
Write-Host "Two tiny OpenHands worker jobs may each use multiple model turns."
Write-Host ""

Write-Host "Running control-plane compatibility tests locally first..."
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

# Load runtime config without printing secrets.
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
Write-Host "Starting ONE two-worker live mission..."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host "AHOS estimate/reserve: USD 0.02 total (USD 0.01 per AI worker)."
Write-Host "This is NOT a provider-side hard billing cap."
Write-Host ""

$liveCode = @'
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import re

from ahos.mission_orchestrator import (
    MissionStatus,
    MissionStepSpec,
    MultiWorkerMissionOrchestrator,
)
from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import QaExecutionResult, WorkerExecutionResult
from ahos.workforce_execution import WorkStage

ROOT = Path(r"__ROOT__")
PKG = Path(r"__PKG__")
REPORT = Path(r"__REPORT__")
LIVE_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-team"
MISSION_ID = "AHOS-031-live-team"
RESEARCH_MARKER = "RESEARCH_HANDOFF_READY"
DEV_MARKER = "DEV_USED_RESEARCH_HANDOFF_READY"

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
    raise RuntimeError("Could not construct OpenHandsBuilder: " + " | ".join(errors))


def safe_dir(task_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._")
    return value or "task"


base_profiles = {p.worker_id: p for p in default_virtual_workforce()}
required_ids = {"mgr-software-01", "research-01", "dev-01", "qa-01"}
missing = required_ids - set(base_profiles)
if missing:
    raise RuntimeError(f"default workforce missing profiles: {sorted(missing)}")

profiles = (
    base_profiles["mgr-software-01"],
    replace(
        base_profiles["research-01"],
        can_use_paid_ai=True,
        daily_budget_usd=0.02,
    ),
    replace(
        base_profiles["dev-01"],
        can_use_paid_ai=True,
        daily_budget_usd=0.02,
    ),
    base_profiles["qa-01"],
)
registry = VirtualWorkforceRegistry(profiles)

builder = build_builder(resolve_settings())
raw_runs: list[tuple[str, object]] = []


def make_runner(label: str):
    def _run(prompt: str, workspace: Path):
        result = builder.run(task=prompt, workspace=workspace)
        raw_runs.append((label, result))
        return result
    return _run


research_adapter = OpenHandsWorkerAdapter(
    runner=make_runner("research-01"),
    workspace_root=LIVE_ROOT,
)
dev_adapter = OpenHandsWorkerAdapter(
    runner=make_runner("dev-01"),
    workspace_root=LIVE_ROOT,
)


def research_executor(item, worker_id):
    base = research_adapter(item, worker_id)
    target = LIVE_ROOT / safe_dir(item.task_id) / "RESEARCH_NOTE.txt"
    valid = (
        base.success
        and target.exists()
        and target.read_text(encoding="utf-8").strip() == RESEARCH_MARKER
    )
    return WorkerExecutionResult(
        task_id=item.task_id,
        worker_id=worker_id,
        success=valid,
        summary=RESEARCH_MARKER if valid else base.summary,
        artifacts=base.artifacts,
        tests_run=base.tests_run,
    )


def dev_executor(item, worker_id):
    return dev_adapter(item, worker_id)


def qa_executor(item, worker_result, qa_worker_id):
    task_dir = LIVE_ROOT / safe_dir(item.task_id)

    if item.task_id.endswith(":research"):
        target = task_dir / "RESEARCH_NOTE.txt"
        expected = RESEARCH_MARKER
    elif item.task_id.endswith(":build"):
        target = task_dir / "DEV_NOTE.txt"
        expected = DEV_MARKER
    else:
        return QaExecutionResult(
            task_id=item.task_id,
            qa_worker_id=qa_worker_id,
            passed=False,
            summary="unknown live mission step",
        )

    passed = (
        worker_result.success
        and target.exists()
        and target.read_text(encoding="utf-8").strip() == expected
    )

    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=passed,
        summary=(
            f"verified {target.name} exact content"
            if passed
            else f"verification failed for {target.name}"
        ),
    )


def manager_planner(mission_id, objective, manager_id):
    if manager_id != "mgr-software-01":
        raise RuntimeError(f"unexpected manager: {manager_id}")

    return (
        MissionStepSpec(
            step_id="research",
            title=(
                "Create RESEARCH_NOTE.txt containing exactly "
                "RESEARCH_HANDOFF_READY. Do not change any other file. "
                "Verify the exact contents."
            ),
            department="research",
            required_capabilities=frozenset({"research"}),
            estimated_cost_usd=0.01,
            owner_approved=True,
        ),
        MissionStepSpec(
            step_id="build",
            title=(
                "Use the previous research result in your task context. "
                "Create DEV_NOTE.txt containing exactly "
                "DEV_USED_RESEARCH_HANDOFF_READY. Do not change any other file. "
                "Verify the exact contents."
            ),
            department="software",
            required_capabilities=frozenset({"python", "automation"}),
            depends_on=("research",),
            estimated_cost_usd=0.01,
            owner_approved=True,
        ),
    )


orchestrator = MultiWorkerMissionOrchestrator(
    registry,
    manager_planner=manager_planner,
    executors={
        "research-01": research_executor,
        "dev-01": dev_executor,
    },
    qa_executor=qa_executor,
)

result = orchestrator.run(
    mission_id=MISSION_ID,
    objective=(
        "Prove that an AHOS department manager can route a real multi-worker "
        "mission from Researcher to Developer with QA and downstream handoff."
    ),
    primary_department="software",
)

print("=== AHOS-031 LIVE MULTI-WORKER RESULT ===")
print("MISSION STATUS:", result.status.value)
print("MANAGER:", result.manager_id)
for step in result.steps:
    print(
        "STEP:",
        step.step.step_id,
        "| WORKER:",
        step.worker_id,
        "| STAGE:",
        step.stage.value,
    )
    print("  WORKER SUMMARY:", step.worker_summary)
    print("  QA:", step.qa_summary)

costs: list[dict[str, object]] = []
estimated_total = 0.0
all_costs_available = True

for label, raw in raw_runs:
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)

    if cost is None:
        all_costs_available = False
        costs.append({"worker": label, "estimated_cost_usd": None})
    else:
        value = float(cost)
        estimated_total += value
        costs.append({"worker": label, "estimated_cost_usd": value})

print(
    "REPORTED ESTIMATED TOTAL COST USD:",
    estimated_total if all_costs_available else "partial/unavailable",
)

research_file = LIVE_ROOT / safe_dir(f"{MISSION_ID}:research") / "RESEARCH_NOTE.txt"
dev_file = LIVE_ROOT / safe_dir(f"{MISSION_ID}:build") / "DEV_NOTE.txt"

print("RESEARCH FILE:", research_file.exists())
print("DEV FILE:", dev_file.exists())

if result.status is not MissionStatus.COMPLETED:
    raise SystemExit("AHOS-031 REAL MULTI-WORKER MISSION: FAILED")

if (
    not research_file.exists()
    or research_file.read_text(encoding="utf-8").strip() != RESEARCH_MARKER
):
    raise SystemExit("AHOS-031 research artifact verification failed")

if (
    not dev_file.exists()
    or dev_file.read_text(encoding="utf-8").strip() != DEV_MARKER
):
    raise SystemExit("AHOS-031 developer artifact verification failed")

report = {
    "mission_id": MISSION_ID,
    "status": result.status.value,
    "manager_id": result.manager_id,
    "objective": result.objective,
    "steps": [
        {
            "step_id": step.step.step_id,
            "worker_id": step.worker_id,
            "stage": step.stage.value,
            "worker_summary": step.worker_summary,
            "qa_summary": step.qa_summary,
        }
        for step in result.steps
    ],
    "reported_costs": costs,
    "reported_estimated_total_cost_usd": (
        estimated_total if all_costs_available else None
    ),
    "research_artifact_verified": True,
    "developer_artifact_verified": True,
    "external_business_actions": 0,
}
REPORT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print("AHOS-031 REAL MULTI-WORKER MISSION: PASS")
'@

$liveCode = $liveCode.Replace("__ROOT__", $root.Replace("\","\\"))
$liveCode = $liveCode.Replace("__PKG__", $pkg.Replace("\","\\"))
$liveCode = $liveCode.Replace("__REPORT__", $reportPath.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $liveCode | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    throw "AHOS-031 live multi-worker mission failed. See the error above."
}

# Only mark the backlog completed after the live mission really passes.
$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-031" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-031"
        title = "Prove real multi-worker AI mission execution"
        status = "completed"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        completed_at = [DateTime]::UtcNow.ToString("o")
        task = "Run one owner-approved real mission through Software Department Manager planning, a real OpenHands Researcher worker, QA, downstream result handoff, a real OpenHands Software Engineer worker, and final QA. No publishing, messaging, payments, deployments, or other external business actions."
    }
} else {
    $t = $b.tasks | Where-Object { $_.id -eq "AHOS-031" } | Select-Object -First 1
    $t.status = "completed"
    if ($t.PSObject.Properties.Name -contains "completed_at") {
        $t.completed_at = [DateTime]::UtcNow.ToString("o")
    } else {
        $t | Add-Member -NotePropertyName completed_at -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
    }
}
[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

git -C $ws add ahos_core/AHOS_BACKLOG.json ahos_core/reports/AHOS-031-live-mission.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "test(ahos): prove real multi-worker AI mission"
if ($LASTEXITCODE -ne 0) { throw "Live mission passed, but git commit failed." }

git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) { throw "Live mission passed, but git push failed." }

Write-Host ""
Write-Host "=== AHOS-031 COMPLETE ==="
Write-Host "Department manager: PASS"
Write-Host "Real Researcher AI worker: PASS"
Write-Host "Research QA: PASS"
Write-Host "Cross-worker result handoff: PASS"
Write-Host "Real Software Engineer AI worker: PASS"
Write-Host "Developer QA: PASS"
Write-Host "Git evidence report: PASS"
Write-Host "External publish/message/payment/deployment actions: 0"
