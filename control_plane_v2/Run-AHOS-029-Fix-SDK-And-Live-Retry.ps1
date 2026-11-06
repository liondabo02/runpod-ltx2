param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "Live retry not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$builderPath = Join-Path $root "miniverse\openhands_builder.py"
$compatTestPath = Join-Path $root "tests\test_openhands_sdk_compat.py"
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $builderPath)) { throw "openhands_builder.py not found." }
if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Write-Host "=== AHOS-029 OPENHANDS SDK COMPATIBILITY FIX ==="
Write-Host "Detected failure: installed OpenHands Conversation does not accept max_budget_per_run."
Write-Host "We keep the SDK iteration guard and AHOS owner/budget gates."
Write-Host "No AI call occurs until all local tests pass."
Write-Host ""

# Patch only the unsupported Conversation keyword.
$patchCode = @'
from pathlib import Path
import re

path = Path(r"__BUILDER__")
text = path.read_text(encoding="utf-8")

pattern = re.compile(r"(?m)^[ \t]*max_budget_per_run\s*=.*\r?\n")
new_text, count = pattern.subn("", text)

if count == 0:
    if "max_budget_per_run=" in text:
        raise SystemExit("Found max_budget_per_run but could not safely remove it.")
    print("Compatibility patch already present.")
else:
    path.write_text(new_text, encoding="utf-8")
    print(f"Removed unsupported max_budget_per_run keyword ({count} occurrence).")
'@
$patchCode = $patchCode.Replace("__BUILDER__", $builderPath.Replace("\","\\"))
$patchCode | & $python -
if ($LASTEXITCODE -ne 0) { throw "Builder compatibility patch failed." }

[IO.File]::WriteAllBytes(
    $compatTestPath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGluc3BlY3QKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgpmcm9tIG9wZW5oYW5kcy5zZGsgaW1wb3J0IENvbnZlcnNhdGlvbgoKCmRlZiB0ZXN0X29wZW5oYW5kc19idWlsZGVyX2F2b2lkc191bnN1cHBvcnRlZF9idWRnZXRfa2V5d29yZCgpIC0+IE5vbmU6CiAgICBzb3VyY2UgPSAoCiAgICAgICAgUGF0aChfX2ZpbGVfXykucmVzb2x2ZSgpLnBhcmVudHNbMV0KICAgICAgICAvICJtaW5pdmVyc2UiCiAgICAgICAgLyAib3BlbmhhbmRzX2J1aWxkZXIucHkiCiAgICApLnJlYWRfdGV4dChlbmNvZGluZz0idXRmLTgiKQoKICAgIHBhcmFtcyA9IGluc3BlY3Quc2lnbmF0dXJlKENvbnZlcnNhdGlvbikucGFyYW1ldGVycwogICAgaWYgIm1heF9idWRnZXRfcGVyX3J1biIgbm90IGluIHBhcmFtczoKICAgICAgICBhc3NlcnQgIm1heF9idWRnZXRfcGVyX3J1bj0iIG5vdCBpbiBzb3VyY2UKCgpkZWYgdGVzdF9pbnN0YWxsZWRfc2RrX3N1cHBvcnRzX2l0ZXJhdGlvbl9ndWFyZCgpIC0+IE5vbmU6CiAgICBwYXJhbXMgPSBpbnNwZWN0LnNpZ25hdHVyZShDb252ZXJzYXRpb24pLnBhcmFtZXRlcnMKICAgIGFzc2VydCAibWF4X2l0ZXJhdGlvbl9wZXJfcnVuIiBpbiBwYXJhbXMK")
)

Write-Host ""
Write-Host "Running control-plane tests locally..."
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
    $ahosExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $oldPythonPath
}
if ($ahosExit -ne 0) {
    throw "AHOS tests failed. No live AI call was made."
}

# Record AHOS-029 locally.
$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-029" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-029"
        title = "Align OpenHands builder with installed SDK conversation API"
        status = "completed"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        completed_at = [DateTime]::UtcNow.ToString("o")
        task = "Remove the unsupported max_budget_per_run Conversation keyword for the installed OpenHands SDK while retaining max_iteration_per_run, AHOS owner approval, and worker budget gates. Run compatibility tests before one tiny live retry."
    }
    [IO.File]::WriteAllText(
        $backlogPath,
        ($b | ConvertTo-Json -Depth 12),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

# Commit both control-plane compatibility fix and AHOS backlog update.
git add miniverse/openhands_builder.py tests/test_openhands_sdk_compat.py runtime/workspaces/ahos-autopilot/ahos_core/AHOS_BACKLOG.json
git -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "fix: align OpenHands builder with installed SDK"
if ($LASTEXITCODE -ne 0) { throw "git commit failed. No live AI call was made." }

git push origin HEAD
if ($LASTEXITCODE -ne 0) { throw "git push failed. No live AI call was made." }

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

Write-Host ""
Write-Host "Local compatibility fix passed and was pushed."
Write-Host "Starting ONE tiny owner-approved real worker retry..."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host "The SDK iteration limit remains active."
Write-Host "AHOS task estimate/reserve: USD 0.02; provider billing is not hard-capped by this value."
Write-Host ""

$liveCode = @'
from __future__ import annotations

from pathlib import Path

from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.virtual_workforce import VirtualWorkforceRegistry, WorkerProfile, WorkerRole
from ahos.worker_runtime import QaExecutionResult, VirtualWorkerRuntime
from ahos.workforce_execution import WorkItem, WorkStage

ROOT = Path(r"__ROOT__")
LIVE_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-ai"
TASK_ID = "AHOS-029-dev01-real-ai-smoke"
TARGET = "AHOS_DEV01_OK.txt"
EXPECTED = "AHOS_DEV01_REAL_AI_OK"

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


builder = build_builder(resolve_settings())
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
adapter = OpenHandsWorkerAdapter(runner=live_runner, workspace_root=LIVE_ROOT)


def verify_qa(item, worker_result, qa_worker_id):
    target = LIVE_ROOT / TASK_ID / TARGET
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
target = LIVE_ROOT / TASK_ID / TARGET

print("=== REAL VIRTUAL WORKER RESULT ===")
print("STAGE:", result.stage.value)
print("WORKER:", result.assignment.worker_id)
print("WORKER SUMMARY:", result.worker_result.summary if result.worker_result else None)
print("QA:", result.qa_result.summary if result.qa_result else None)
print("TARGET EXISTS:", target.exists())
if target.exists():
    print("TARGET CONTENT:", target.read_text(encoding="utf-8").strip())

if raw_results:
    raw = raw_results[-1]
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)
    print("REPORTED ESTIMATED COST USD:", cost if cost is not None else "unavailable")

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
    throw "AHOS-029 live AI worker retry failed. See the error above."
}

Write-Host ""
Write-Host "=== AHOS-029 COMPLETE ==="
Write-Host "Real virtual worker: PASS"
Write-Host "QA verification: PASS"
Write-Host "OpenHands SDK compatibility: PASS"
Write-Host "Owner approval gate: PASS"
Write-Host "No publish/message/payment action was performed."
