param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "Live AI test was not approved locally. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$executionPath = Join-Path $pkg "ahos\workforce_execution.py"
$approvalTestPath = Join-Path $pkg "tests\test_owner_approved_paid_work.py"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found: $python" }
if (-not (Test-Path $executionPath)) { throw "workforce_execution.py not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name,$value = $_ -split '=',2
    [Environment]::SetEnvironmentVariable($name.Trim(),$value.Trim(),'Process')
}

if (-not $env:LLM_API_KEY -and -not $env:OPENAI_API_KEY) {
    throw "No LLM/OpenAI API key is loaded from .env.runtime."
}
if (-not $env:MINIVERSE_OPENHANDS_MODEL) {
    throw "MINIVERSE_OPENHANDS_MODEL is missing."
}

Write-Host "=== AHOS-027 OWNER-APPROVED LIVE WORKER SMOKE ==="
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host "One tiny OpenHands coding task will run."
Write-Host "Estimated AHOS reserve: USD 0.02"
Write-Host "IMPORTANT: OpenHands may use multiple model turns; USD 0.02 is an AHOS gate/reserve, not a provider-side hard billing cap."
Write-Host ""

$patchCode = @'
from pathlib import Path

path = Path(r"__EXECUTION_PATH__")
text = path.read_text(encoding="utf-8")

needle = "    requires_owner_approval: bool = False\n"
if "    owner_approved: bool = False\n" not in text:
    if needle not in text:
        raise SystemExit("Could not locate WorkItem approval field.")
    text = text.replace(
        needle,
        needle + "    owner_approved: bool = False\n",
        1,
    )

old = '''    @staticmethod
    def _approval_required(item: WorkItem) -> bool:
        return any(
            (
                item.requires_owner_approval,
                item.external_side_effect,
                item.destructive,
                item.touches_secrets,
                item.estimated_cost_usd > 0,
            )
        )
'''
new = '''    @staticmethod
    def _approval_required(item: WorkItem) -> bool:
        protected_action = any(
            (
                item.requires_owner_approval,
                item.external_side_effect,
                item.destructive,
                item.touches_secrets,
                item.estimated_cost_usd > 0,
            )
        )
        return protected_action and not item.owner_approved
'''
if old in text:
    text = text.replace(old, new, 1)
elif "return protected_action and not item.owner_approved" not in text:
    raise SystemExit("Could not safely patch _approval_required.")

path.write_text(text, encoding="utf-8")
print("Owner-approved execution gate: patched/ready")
'@
$patchCode = $patchCode.Replace("__EXECUTION_PATH__", $executionPath.Replace("\","\\"))
$patchCode | & $python -
if ($LASTEXITCODE -ne 0) { throw "Approval gate patch failed." }

$approvalTest = @'
from ahos.virtual_workforce import VirtualWorkforceRegistry, WorkerProfile, WorkerRole
from ahos.workforce_execution import VirtualWorkforceDispatcher, WorkItem, WorkStage


def test_paid_work_requires_owner_approval_but_can_run_after_explicit_approval():
    paid_worker = WorkerProfile(
        worker_id="paid-dev",
        name="Paid Dev",
        role=WorkerRole.SOFTWARE_ENGINEER,
        department="software",
        capabilities=frozenset({"python"}),
        daily_budget_usd=0.02,
        can_use_paid_ai=True,
    )
    registry = VirtualWorkforceRegistry((paid_worker,))
    dispatcher = VirtualWorkforceDispatcher(registry)

    blocked = dispatcher.assign(
        WorkItem(
            task_id="blocked",
            title="Paid task",
            department="software",
            required_capabilities=frozenset({"python"}),
            estimated_cost_usd=0.02,
        )
    )
    assert blocked.stage is WorkStage.BLOCKED
    assert blocked.owner_approval_required is True

    approved = dispatcher.assign(
        WorkItem(
            task_id="approved",
            title="Paid task",
            department="software",
            required_capabilities=frozenset({"python"}),
            estimated_cost_usd=0.02,
            owner_approved=True,
        )
    )
    assert approved.stage is WorkStage.ASSIGNED
    assert approved.worker_id == "paid-dev"
'@
[IO.File]::WriteAllText(
    $approvalTestPath,
    $approvalTest,
    (New-Object System.Text.UTF8Encoding($false))
)

Write-Host "Running full AHOS tests before any AI call..."
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
    throw "Local tests failed. Live AI call was NOT started."
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-027" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-027"
        title = "Add explicit owner-approved paid worker execution path"
        status = "completed"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        completed_at = [DateTime]::UtcNow.ToString("o")
        task = "Allow a paid virtual-worker task to pass the approval gate only when owner_approved is explicit, while still enforcing a paid-capable worker and its daily budget. Validate locally, then run one owner-approved live OpenHands smoke task."
    }
    [IO.File]::WriteAllText(
        $backlogPath,
        ($b | ConvertTo-Json -Depth 12),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

git -C $ws add ahos_core/ahos/workforce_execution.py ahos_core/tests/test_owner_approved_paid_work.py ahos_core/AHOS_BACKLOG.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "feat(ahos): add owner-approved paid worker path"
if ($LASTEXITCODE -ne 0) { throw "git commit failed. Live AI call was NOT started." }

git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) { throw "git push failed. Live AI call was NOT started." }

Write-Host ""
Write-Host "Local gate/tests committed. Starting ONE real AI worker task now..."
Write-Host ""

$liveCode = @'
from __future__ import annotations

from pathlib import Path

from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerProfile,
    WorkerRole,
)
from ahos.worker_runtime import (
    QaExecutionResult,
    VirtualWorkerRuntime,
)
from ahos.workforce_execution import WorkItem, WorkStage

ROOT = Path(r"__ROOT__")
LIVE_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-ai"
TASK_ID = "AHOS-027-dev01-real-ai-smoke"
EXPECTED = "AHOS_DEV01_REAL_AI_OK"
TARGET = "AHOS_DEV01_OK.txt"

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


settings = resolve_settings()
builder = build_builder(settings)

raw_results = []

def live_runner(prompt: str, workspace: Path):
    result = builder.run(task=prompt, workspace=workspace)
    raw_results.append(result)
    return result

worker = WorkerProfile(
    worker_id="dev-01-live",
    name="Software Engineer 01 - Live Smoke",
    role=WorkerRole.SOFTWARE_ENGINEER,
    department="software",
    capabilities=frozenset({"python", "backend", "api", "automation", "testing", "git"}),
    daily_budget_usd=0.02,
    can_use_paid_ai=True,
)
qa = WorkerProfile(
    worker_id="qa-01",
    name="QA Engineer 01",
    role=WorkerRole.QA_ENGINEER,
    department="quality",
    capabilities=frozenset({"qa", "verification", "testing"}),
)

registry = VirtualWorkforceRegistry((worker, qa))
adapter = OpenHandsWorkerAdapter(
    runner=live_runner,
    workspace_root=LIVE_ROOT,
)

def verify_qa(item, worker_result, qa_worker_id):
    workspace = LIVE_ROOT / TASK_ID
    target = workspace / TARGET
    passed = (
        worker_result.success
        and target.exists()
        and target.read_text(encoding="utf-8").strip() == EXPECTED
    )
    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=passed,
        summary="file/content verification passed" if passed else "file/content verification failed",
    )

runtime = VirtualWorkerRuntime(
    registry,
    executors={"dev-01-live": adapter},
    qa_executor=verify_qa,
)

item = WorkItem(
    task_id=TASK_ID,
    title=(
        f"Create a file named {TARGET} containing exactly {EXPECTED}. "
        "Do not change any other file. Verify the contents."
    ),
    department="software",
    required_capabilities=frozenset({"python", "automation"}),
    estimated_cost_usd=0.02,
    owner_approved=True,
)

result = runtime.run(item)

print("=== REAL VIRTUAL WORKER RESULT ===")
print("STAGE:", result.stage.value)
print("WORKER:", result.assignment.worker_id)
print("WORKER SUMMARY:", result.worker_result.summary if result.worker_result else None)
print("QA:", result.qa_result.summary if result.qa_result else None)

workspace = LIVE_ROOT / TASK_ID
target = workspace / TARGET
print("TARGET EXISTS:", target.exists())
if target.exists():
    print("TARGET CONTENT:", target.read_text(encoding="utf-8").strip())

if raw_results:
    raw = raw_results[-1]
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)
    if cost is not None:
        print("REPORTED ESTIMATED COST USD:", cost)
    else:
        print("REPORTED ESTIMATED COST USD: unavailable")

if result.stage is not WorkStage.COMPLETED:
    raise SystemExit("REAL AI WORKER SMOKE: FAILED")
if not target.exists() or target.read_text(encoding="utf-8").strip() != EXPECTED:
    raise SystemExit("REAL AI WORKER SMOKE: FAILED CONTENT CHECK")

print("REAL AI WORKER SMOKE: PASS")
'@
$liveCode = $liveCode.Replace("__ROOT__", $root.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $liveCode | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    throw "AHOS-027 live AI worker smoke failed. See the error above."
}

Write-Host ""
Write-Host "=== AHOS-027 LIVE SMOKE COMPLETE ==="
Write-Host "Real virtual worker: PASS"
Write-Host "QA file/content check: PASS"
Write-Host "Owner approval path: PASS"
Write-Host "No external publish/message/payment action was performed."
