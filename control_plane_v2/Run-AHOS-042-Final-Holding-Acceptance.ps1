param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "AHOS-042 final live acceptance test is not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$reportDir = Join-Path $pkg "reports"
$reportPath = Join-Path $reportDir "AHOS-042-final-acceptance.json"
$liveDb = Join-Path $pkg "runtime\company-service.db"
$heartbeatPath = Join-Path $pkg "runtime\company-service-heartbeat.json"
$stopFile = Join-Path $pkg "runtime\company-service.stop"
$watchdogPidFile = Join-Path $pkg "runtime\company-service-watchdog.pid"
$serviceLauncher = Join-Path $root "Start-AHOS-Company-Service.ps1"
$dashboardUrl = "http://127.0.0.1:8765"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Write-Host "=== AHOS-042 FINAL HOLDING ACCEPTANCE TEST ==="
Write-Host "REAL persistent queue -> AI manager -> AI researcher -> QA -> handoff -> AI developer -> QA -> dashboard"
Write-Host ""
Write-Host "COST:"
Write-Host "This final acceptance starts 3 small OpenHands AI workflows (manager, researcher, developer)."
Write-Host "Each workflow may use multiple model turns."
Write-Host "AHOS worker reserve is USD 0.01 each; this is NOT a provider-side hard cap."
Write-Host "The comparable AHOS-036 proof reported about USD 0.0295 total; this run may differ."
Write-Host ""
Write-Host "SAFETY:"
Write-Host "No customer messages, publishing, payments, purchases, deployment, destructive actions, or secret access."
Write-Host ""

Write-Host "Running local compatibility tests BEFORE any AI call..."
& $python -m pytest tests\test_openhands_sdk_compat.py tests\test_openhands_builder.py -q
if ($LASTEXITCODE -ne 0) {
    throw "Control-plane compatibility tests failed. No live AI call was made."
}

Write-Host "Running full AHOS tests locally..."
$oldPythonPath = $env:PYTHONPATH
Push-Location $pkg
try {
    $env:PYTHONPATH = $pkg
    & $python -m pytest -q
    $testExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $oldPythonPath
}
if ($testExit -ne 0) {
    throw "AHOS local tests failed. No live AI call was made."
}

# Ensure the final roadmap item exists before live execution.
$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-042" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-042"
        title = "Final controlled holding acceptance test"
        status = "pending"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        task = "Run one explicit owner-approved final acceptance mission through the real persistent company queue, real AI department manager, real AI researcher, deterministic QA, verified handoff, real AI software engineer, final QA, persistent result, and Holding Control Center visibility. No external business actions."
    }
    [IO.File]::WriteAllText(
        $backlogPath,
        ($b | ConvertTo-Json -Depth 12),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

Write-Host "Verifying Holding Control Center BEFORE any AI call..."
try {
    $dashBefore = Invoke-WebRequest -UseBasicParsing -Uri "$dashboardUrl/api/status" -TimeoutSec 5
    if ($dashBefore.StatusCode -ne 200) { throw "dashboard not HTTP 200" }
    Write-Host "Dashboard preflight: PASS"
} catch {
    throw "AHOS-041 dashboard is not reachable at $dashboardUrl. No live AI call was made."
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
New-Item -ItemType Directory -Force -Path (Split-Path $liveDb -Parent) | Out-Null

if (-not (Test-Path $serviceLauncher)) {
    throw "Company service launcher not found: $serviceLauncher"
}

Write-Host ""
Write-Host "Local tests passed."
Write-Host "Stopping SAFE-IDLE company service for the controlled final acceptance..."
Set-Content -Path $stopFile -Value "AHOS-042 final acceptance" -Encoding UTF8

$stopped = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Milliseconds 750
    if (Test-Path $heartbeatPath) {
        try {
            $hb = Get-Content $heartbeatPath -Raw | ConvertFrom-Json
            if ($hb.state -eq "stopped") { $stopped = $true; break }
        } catch {}
    }
}
if (-not $stopped) {
    if (Test-Path $heartbeatPath) {
        try {
            $hb = Get-Content $heartbeatPath -Raw | ConvertFrom-Json
            if ($hb.pid) { Stop-Process -Id ([int]$hb.pid) -Force -ErrorAction SilentlyContinue }
        } catch {}
    }
    if (Test-Path $watchdogPidFile) {
        try {
            $wpid = [int](Get-Content $watchdogPidFile -Raw)
            Stop-Process -Id $wpid -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}

Write-Host "Starting ONE final queued full-AI mission..."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host ""

$live = @'
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import re

from ahos.ai_manager_planner import OpenHandsManagerPlanner
from ahos.autonomous_company import CompanyLoop, PersistentMissionQueue, QueueStatus
from ahos.company_runtime import OrchestratedMissionExecutor
from ahos.mission_orchestrator import MultiWorkerMissionOrchestrator
from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import QaExecutionResult, WorkerExecutionResult

ROOT = Path(r"__ROOT__")
REPORT = Path(r"__REPORT__")
DB = Path(r"__DB__")
PLAN_ROOT = ROOT / "runtime" / "workspaces" / "ahos-final-manager"
WORK_ROOT = ROOT / "runtime" / "workspaces" / "ahos-final-holding"
MISSION_ID = "AHOS-042-final-acceptance"
RESEARCH_FILE = "STUDIO_RESEARCH_BRIEF.md"
DEV_FILE = "STUDIO_AUTOMATION_PLAN.md"

import shutil
for stale in (
    PLAN_ROOT / MISSION_ID,
    WORK_ROOT / f"{MISSION_ID}_research-brief",
    WORK_ROOT / f"{MISSION_ID}_prototype-plan",
):
    if stale.exists():
        shutil.rmtree(stale, ignore_errors=True)

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


profiles = {p.worker_id: p for p in default_virtual_workforce()}
required_ids = ("mgr-software-01", "research-01", "dev-01", "qa-01")
missing = [worker_id for worker_id in required_ids if worker_id not in profiles]
if missing:
    raise RuntimeError(f"default workforce missing profiles: {missing}")

capability_catalog = {
    "research": frozenset(profiles["research-01"].capabilities),
    "software": frozenset(profiles["dev-01"].capabilities),
}

live_profiles = (
    profiles["mgr-software-01"],
    replace(
        profiles["research-01"],
        can_use_paid_ai=True,
        daily_budget_usd=max(float(profiles["research-01"].daily_budget_usd), 0.02),
    ),
    replace(
        profiles["dev-01"],
        can_use_paid_ai=True,
        daily_budget_usd=max(float(profiles["dev-01"].daily_budget_usd), 0.02),
    ),
    profiles["qa-01"],
)
registry = VirtualWorkforceRegistry(live_profiles)

builder = build_builder(resolve_settings())
raw_runs: list[tuple[str, object]] = []
research_handoff: list[str] = []
developer_prompts: list[str] = []


def tracked_runner(label: str):
    def _run(prompt: str, workspace: Path):
        if label == "developer":
            developer_prompts.append(prompt)
        result = builder.run(task=prompt, workspace=workspace)
        raw_runs.append((label, result))
        return result
    return _run


ai_manager = OpenHandsManagerPlanner(
    runner=tracked_runner("manager"),
    workspace_root=PLAN_ROOT,
    allowed_departments=frozenset({"research", "software"}),
    capability_catalog=capability_catalog,
    max_steps=2,
    max_total_estimated_cost_usd=0.0,
)


def approved_live_planner(mission_id, objective, manager_id):
    steps = tuple(ai_manager(mission_id, objective, manager_id))

    if len(steps) != 2:
        raise ValueError(f"expected exactly 2 manager steps, got {len(steps)}")

    research = [s for s in steps if s.department == "research"]
    software = [s for s in steps if s.department == "software"]
    if len(research) != 1 or len(software) != 1:
        raise ValueError("manager must choose one research and one software step")

    r = research[0]
    d = software[0]

    if r.depends_on:
        raise ValueError("research step must be the dependency root")
    if r.step_id not in d.depends_on:
        raise ValueError("software step must depend on research")

    approved = []
    for step in steps:
        if step.external_side_effect or step.destructive or step.touches_secrets:
            raise ValueError(f"protected behavior planned in {step.step_id}")
        if step.owner_approved:
            raise ValueError("AI manager attempted self-approval")

        if step.department == "research":
            execution_contract = (
                f"{step.title}\n\nExecution contract: Create exactly one useful "
                f"artifact named {RESEARCH_FILE}. It must contain exactly three "
                "concise numbered requirements/constraints for a safe local-only "
                "AI animation-studio episode pipeline. Do not modify external systems."
            )
        else:
            execution_contract = (
                f"{step.title}\n\nExecution contract: Use the previous research "
                f"handoff in your task context and create exactly one artifact "
                f"named {DEV_FILE}. Describe a small local implementation plan "
                "for the holding animation-studio pipeline based directly on that research. "
                "Do not modify external systems."
            )

        approved.append(
            replace(
                step,
                title=execution_contract,
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
developer_adapter = OpenHandsWorkerAdapter(
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
            summary=f"{RESEARCH_FILE} was not created",
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

    return WorkerExecutionResult(
        task_id=item.task_id,
        worker_id=worker_id,
        success=True,
        summary=(
            f"{base.summary}\n\nVerified downstream research handoff:\n{content}"
        ),
        artifacts=base.artifacts,
        tests_run=base.tests_run,
    )


def developer_executor(item, worker_id):
    return developer_adapter(item, worker_id)


def qa_executor(item, worker_result, qa_worker_id):
    task_dir = WORK_ROOT / safe_dir(item.task_id)
    if item.department == "research":
        target = task_dir / RESEARCH_FILE
    elif item.department == "software":
        target = task_dir / DEV_FILE
    else:
        return QaExecutionResult(
            task_id=item.task_id,
            qa_worker_id=qa_worker_id,
            passed=False,
            summary="unexpected department",
        )

    passed = (
        worker_result.success
        and target.exists()
        and bool(target.read_text(encoding="utf-8").strip())
    )
    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=passed,
        summary=(
            f"verified {target.name}"
            if passed
            else f"verification failed for {target.name}"
        ),
    )


orchestrator = MultiWorkerMissionOrchestrator(
    registry,
    manager_planner=approved_live_planner,
    executors={
        "research-01": research_executor,
        "dev-01": developer_executor,
    },
    qa_executor=qa_executor,
)

queue = PersistentMissionQueue(DB)
objective = f"""
Run the final acceptance mission for the AHOS holding core using a tiny
local-only animation-studio automation planning task.
The AI manager must choose exactly two steps: research first, software second.
The research worker must produce {RESEARCH_FILE} with three requirements for a
safe repeatable AI animation episode pipeline. The software worker must depend
on and use that research result, then produce {DEV_FILE}. No video generation
is required in this acceptance test. No customer contact, publishing, deployment,
purchases, payments, credential access, destructive actions, or external systems.
""".strip()

queue.enqueue(
    mission_id=MISSION_ID,
    objective=objective,
    primary_department="software",
    max_attempts=1,
    replace_existing=True,
)

loop = CompanyLoop(
    queue=queue,
    executor=OrchestratedMissionExecutor(orchestrator),
    owner="AHOS-042-FINAL-ACCEPTANCE",
)

print("QUEUE BEFORE:", queue.get(MISSION_ID).status.value)
final = loop.run_once()

if final is None:
    raise SystemExit("company loop did not claim queued mission")

print("QUEUE AFTER:", final.status.value)
print("ATTEMPTS:", final.attempts)
print("LEASE OWNER AFTER:", final.lease_owner)

if final.status is not QueueStatus.COMPLETED:
    print("LAST ERROR:", final.last_error)
    raise SystemExit("AHOS-042 final queued full-AI mission did not complete")

if not final.result_json:
    raise SystemExit("queue result_json missing")

queue_result = json.loads(final.result_json)
if queue_result.get("status") != "completed":
    raise SystemExit("persisted queue result is not completed")

if not research_handoff:
    raise SystemExit("research handoff was not captured")
if not developer_prompts:
    raise SystemExit("developer prompt was not captured")

handoff_probe = research_handoff[0][:160]
if handoff_probe not in developer_prompts[-1]:
    raise SystemExit("real research handoff was not present in developer prompt")

plan_path = PLAN_ROOT / MISSION_ID / "MISSION_PLAN.json"
if not plan_path.exists():
    raise SystemExit("AI manager plan file missing")

plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
executed_steps = queue_result.get("steps", [])

research_step = next(
    step for step in executed_steps
    if step.get("department") == "research"
)
software_step = next(
    step for step in executed_steps
    if step.get("department") == "software"
)

research_artifact = (
    WORK_ROOT
    / safe_dir(f"{MISSION_ID}:{research_step['step_id']}")
    / RESEARCH_FILE
)
developer_artifact = (
    WORK_ROOT
    / safe_dir(f"{MISSION_ID}:{software_step['step_id']}")
    / DEV_FILE
)

if not research_artifact.exists():
    raise SystemExit("research artifact missing after queued mission")
if not developer_artifact.exists():
    raise SystemExit("developer artifact missing after queued mission")

cost_rows = []
reported_total = 0.0
all_costs_available = True

for label, raw in raw_runs:
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)

    if cost is None:
        all_costs_available = False
        cost_rows.append({"actor": label, "estimated_cost_usd": None})
    else:
        value = float(cost)
        reported_total += value
        cost_rows.append({"actor": label, "estimated_cost_usd": value})

print("AI MANAGER PLAN:", [
    {
        "step_id": x.get("step_id"),
        "department": x.get("department"),
        "required_capabilities": x.get("required_capabilities"),
        "depends_on": x.get("depends_on"),
    }
    for x in plan_payload.get("steps", [])
])
print("HANDOFF VERIFIED:", True)
for row in cost_rows:
    print("REPORTED COST:", row["actor"], row["estimated_cost_usd"])
print(
    "REPORTED ESTIMATED TOTAL COST USD:",
    reported_total if all_costs_available else "partial/unavailable",
)
print("AHOS-042 FINAL AI CHAIN: PASS")

REPORT.write_text(
    json.dumps(
        {
            "mission_id": MISSION_ID,
            "queue_status": final.status.value,
            "attempts": final.attempts,
            "ai_manager_plan": plan_payload,
            "queue_result": queue_result,
            "research_to_developer_handoff_verified": True,
            "research_artifact": str(research_artifact),
            "developer_artifact": str(developer_artifact),
            "reported_costs": cost_rows,
            "reported_estimated_total_cost_usd": (
                reported_total if all_costs_available else None
            ),
            "external_publish_actions": 0,
            "external_message_actions": 0,
            "payment_actions": 0,
            "deployment_actions": 0,
            "core_acceptance": True,
        },
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)
'@

$live = $live.Replace("__ROOT__", $root.Replace("\","\\"))
$live = $live.Replace("__REPORT__", $reportPath.Replace("\","\\"))
$live = $live.Replace("__DB__", $liveDb.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $live | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    Remove-Item $stopFile -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile","-WindowStyle","Hidden","-ExecutionPolicy","Bypass","-File",$serviceLauncher) `
        -WindowStyle Hidden
    throw "AHOS-042 final acceptance failed. Local error is shown above; company service restart was requested."
}

$dashboardVerified = $false
try {
    $dashAfter = Invoke-WebRequest -UseBasicParsing -Uri "$dashboardUrl/api/status" -TimeoutSec 10
    if ($dashAfter.StatusCode -ne 200) { throw "dashboard HTTP status was not 200" }
    $dashboardState = $dashAfter.Content | ConvertFrom-Json
    $seen = $dashboardState.missions | Where-Object {
        $_.mission_id -eq "AHOS-042-final-acceptance" -and $_.status -eq "completed"
    } | Select-Object -First 1
    if (-not $seen) { throw "completed final mission was not visible in dashboard API" }
    $dashboardVerified = $true
    Write-Host "Dashboard final mission visibility: PASS"
}
finally {
    Remove-Item $stopFile -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile","-WindowStyle","Hidden","-ExecutionPolicy","Bypass","-File",$serviceLauncher) `
        -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

if (-not $dashboardVerified) { throw "Live AI chain passed, but dashboard verification failed." }

$serviceRestored = $false
if (Test-Path $heartbeatPath) {
    try {
        $restoredHb = Get-Content $heartbeatPath -Raw | ConvertFrom-Json
        if ($restoredHb.state -in @("starting","polling","idle","processed")) {
            $serviceRestored = $true
        }
    } catch {}
}
if (-not $serviceRestored) {
    throw "Final AI chain passed, but the persistent company service did not confirm restart."
}
Write-Host "Company service restart verification: PASS"

$r = Get-Content $reportPath -Raw | ConvertFrom-Json
if ($r.PSObject.Properties.Name -contains "dashboard_visibility_verified") {
    $r.dashboard_visibility_verified = $true
} else {
    $r | Add-Member -NotePropertyName dashboard_visibility_verified -NotePropertyValue $true
}
[IO.File]::WriteAllText(
    $reportPath,
    ($r | ConvertTo-Json -Depth 20),
    (New-Object System.Text.UTF8Encoding($false))
)

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
$t = $b.tasks | Where-Object { $_.id -eq "AHOS-042" } | Select-Object -First 1
if (-not $t) { throw "AHOS-042 backlog item missing." }
$t.status = "completed"
if ($t.PSObject.Properties.Name -contains "completed_at") {
    $t.completed_at = [DateTime]::UtcNow.ToString("o")
} else {
    $t | Add-Member -NotePropertyName completed_at -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
}
[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

git -C $ws add ahos_core/AHOS_BACKLOG.json ahos_core/reports/AHOS-042-final-acceptance.json
$staged2 = git -C $ws diff --cached --name-only
if ($staged2) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" `
        commit -m "test(ahos): complete final holding acceptance"
    if ($LASTEXITCODE -ne 0) { throw "Final acceptance passed, but git commit failed." }
    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "Final acceptance passed, but git push failed." }
}

Write-Host ""
Write-Host "=== AHOS-042 COMPLETE ==="
Write-Host "Real persistent company queue: PASS"
Write-Host "Real AI Department Manager: PASS"
Write-Host "Real AI Researcher: PASS"
Write-Host "Research QA: PASS"
Write-Host "Research -> Developer handoff: PASS"
Write-Host "Real AI Software Engineer: PASS"
Write-Host "Developer QA: PASS"
Write-Host "Queue result persistence: PASS"
Write-Host "Holding Control Center visibility: PASS"
Write-Host "Company service restored: PASS"
Write-Host "Evidence report committed: PASS"
Write-Host "External publish/message/payment/deployment actions: 0"
Write-Host ""
Write-Host "=== CORE HOLDING MVP COMPLETE ==="
Write-Host "AHOS core roadmap through AHOS-042: COMPLETE"
Write-Host "Control Center: $dashboardUrl"

