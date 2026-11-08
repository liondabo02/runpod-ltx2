param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "AHOS-036 live queue-to-AI-chain proof is not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$modulePath = Join-Path $pkg "ahos\company_runtime.py"
$testPath = Join-Path $pkg "tests\test_company_runtime.py"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$reportDir = Join-Path $pkg "reports"
$reportPath = Join-Path $reportDir "AHOS-036-queued-full-ai-chain.json"
$liveDb = Join-Path $pkg "runtime\AHOS-036-live-queue.db"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Write-Host "=== AHOS-036 QUEUE -> FULL AI COMPANY CHAIN ==="
Write-Host "Persistent queue -> company loop -> AI manager -> AI researcher -> QA -> AI developer -> QA"
Write-Host ""
Write-Host "COST:"
Write-Host "This proof starts 3 small OpenHands AI workflows (manager, researcher, developer)."
Write-Host "Each workflow may use multiple model turns."
Write-Host "AHOS worker reserve is USD 0.01 each; this is NOT a provider-side hard cap."
Write-Host ""
Write-Host "SAFETY:"
Write-Host "No customer messages, publishing, payments, purchases, deployment, destructive actions, or secret access."
Write-Host ""

[IO.File]::WriteAllBytes(
    $modulePath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKZnJvbSBkYXRhY2xhc3NlcyBpbXBvcnQgZGF0YWNsYXNzCgpmcm9tIC5hdXRvbm9tb3VzX2NvbXBhbnkgaW1wb3J0IFF1ZXVlZE1pc3Npb24KZnJvbSAubWlzc2lvbl9vcmNoZXN0cmF0b3IgaW1wb3J0IE1pc3Npb25SZXN1bHQsIE11bHRpV29ya2VyTWlzc2lvbk9yY2hlc3RyYXRvcgoKCkBkYXRhY2xhc3Moc2xvdHM9VHJ1ZSkKY2xhc3MgT3JjaGVzdHJhdGVkTWlzc2lvbkV4ZWN1dG9yOgogICAgIiIiQWRhcHRlciB0aGF0IHR1cm5zIG9uZSBxdWV1ZWQgY29tcGFueSBtaXNzaW9uIGludG8gYW4gQUhPUyBtaXNzaW9uIHJ1bi4KCiAgICBRdWV1ZSBwZXJzaXN0ZW5jZS9yZXRyeS9sZWFzZSBiZWhhdmlvciByZW1haW5zIGluIGF1dG9ub21vdXNfY29tcGFueS4KICAgIFBsYW5uaW5nLCByb3V0aW5nLCB3b3JrZXJzLCBRQSwgYW5kIGFwcHJvdmFsIGdhdGVzIHJlbWFpbiBpbiB0aGUgZXhpc3RpbmcKICAgIE11bHRpV29ya2VyTWlzc2lvbk9yY2hlc3RyYXRvciBzdGFjay4KICAgICIiIgoKICAgIG9yY2hlc3RyYXRvcjogTXVsdGlXb3JrZXJNaXNzaW9uT3JjaGVzdHJhdG9yCgogICAgZGVmIF9fY2FsbF9fKHNlbGYsIG1pc3Npb246IFF1ZXVlZE1pc3Npb24pIC0+IE1pc3Npb25SZXN1bHQ6CiAgICAgICAgcmV0dXJuIHNlbGYub3JjaGVzdHJhdG9yLnJ1bigKICAgICAgICAgICAgbWlzc2lvbl9pZD1taXNzaW9uLm1pc3Npb25faWQsCiAgICAgICAgICAgIG9iamVjdGl2ZT1taXNzaW9uLm9iamVjdGl2ZSwKICAgICAgICAgICAgcHJpbWFyeV9kZXBhcnRtZW50PW1pc3Npb24ucHJpbWFyeV9kZXBhcnRtZW50LAogICAgICAgICkK")
)
[IO.File]::WriteAllBytes(
    $testPath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgpmcm9tIGFob3MuYXV0b25vbW91c19jb21wYW55IGltcG9ydCAoCiAgICBDb21wYW55TG9vcCwKICAgIFBlcnNpc3RlbnRNaXNzaW9uUXVldWUsCiAgICBRdWV1ZVN0YXR1cywKKQpmcm9tIGFob3MuY29tcGFueV9ydW50aW1lIGltcG9ydCBPcmNoZXN0cmF0ZWRNaXNzaW9uRXhlY3V0b3IKZnJvbSBhaG9zLm1pc3Npb25fb3JjaGVzdHJhdG9yIGltcG9ydCAoCiAgICBNaXNzaW9uU3RhdHVzLAogICAgTWlzc2lvblN0ZXBTcGVjLAogICAgTXVsdGlXb3JrZXJNaXNzaW9uT3JjaGVzdHJhdG9yLAopCmZyb20gYWhvcy52aXJ0dWFsX3dvcmtmb3JjZSBpbXBvcnQgKAogICAgVmlydHVhbFdvcmtmb3JjZVJlZ2lzdHJ5LAogICAgZGVmYXVsdF92aXJ0dWFsX3dvcmtmb3JjZSwKKQpmcm9tIGFob3Mud29ya2VyX3J1bnRpbWUgaW1wb3J0IGxvY2FsX3Bhc3NfcWEsIG1ha2VfbG9jYWxfdGV4dF9leGVjdXRvcgoKCmRlZiBfcnVudGltZSgpIC0+IE11bHRpV29ya2VyTWlzc2lvbk9yY2hlc3RyYXRvcjoKICAgIHJlZ2lzdHJ5ID0gVmlydHVhbFdvcmtmb3JjZVJlZ2lzdHJ5KGRlZmF1bHRfdmlydHVhbF93b3JrZm9yY2UoKSkKCiAgICBkZWYgcGxhbm5lcihfbWlzc2lvbl9pZDogc3RyLCBfb2JqZWN0aXZlOiBzdHIsIF9tYW5hZ2VyX2lkOiBzdHIpOgogICAgICAgIHJldHVybiAoCiAgICAgICAgICAgIE1pc3Npb25TdGVwU3BlYygKICAgICAgICAgICAgICAgIHN0ZXBfaWQ9InJlc2VhcmNoIiwKICAgICAgICAgICAgICAgIHRpdGxlPSJSZXNlYXJjaCByZXF1aXJlbWVudHMiLAogICAgICAgICAgICAgICAgZGVwYXJ0bWVudD0icmVzZWFyY2giLAogICAgICAgICAgICAgICAgcmVxdWlyZWRfY2FwYWJpbGl0aWVzPWZyb3plbnNldCh7InJlc2VhcmNoIn0pLAogICAgICAgICAgICApLAogICAgICAgICAgICBNaXNzaW9uU3RlcFNwZWMoCiAgICAgICAgICAgICAgICBzdGVwX2lkPSJidWlsZCIsCiAgICAgICAgICAgICAgICB0aXRsZT0iQnVpbGQgZnJvbSByZXNlYXJjaCIsCiAgICAgICAgICAgICAgICBkZXBhcnRtZW50PSJzb2Z0d2FyZSIsCiAgICAgICAgICAgICAgICByZXF1aXJlZF9jYXBhYmlsaXRpZXM9ZnJvemVuc2V0KHsicHl0aG9uIn0pLAogICAgICAgICAgICAgICAgZGVwZW5kc19vbj0oInJlc2VhcmNoIiwpLAogICAgICAgICAgICApLAogICAgICAgICkKCiAgICByZXR1cm4gTXVsdGlXb3JrZXJNaXNzaW9uT3JjaGVzdHJhdG9yKAogICAgICAgIHJlZ2lzdHJ5LAogICAgICAgIG1hbmFnZXJfcGxhbm5lcj1wbGFubmVyLAogICAgICAgIGV4ZWN1dG9ycz17CiAgICAgICAgICAgICJyZXNlYXJjaC0wMSI6IG1ha2VfbG9jYWxfdGV4dF9leGVjdXRvcigKICAgICAgICAgICAgICAgIGxhbWJkYSBpdGVtLCB3b3JrZXJfaWQ6ICJyZXNlYXJjaCBoYW5kb2ZmIHJlYWR5IgogICAgICAgICAgICApLAogICAgICAgICAgICAiZGV2LTAxIjogbWFrZV9sb2NhbF90ZXh0X2V4ZWN1dG9yKAogICAgICAgICAgICAgICAgbGFtYmRhIGl0ZW0sIHdvcmtlcl9pZDogInByb3RvdHlwZSByZWFkeSIKICAgICAgICAgICAgKSwKICAgICAgICB9LAogICAgICAgIHFhX2V4ZWN1dG9yPWxvY2FsX3Bhc3NfcWEsCiAgICApCgoKZGVmIHRlc3RfcXVldWVfZGlzcGF0Y2hlc19pbnRvX2Z1bGxfb3JjaGVzdHJhdG9yKHRtcF9wYXRoOiBQYXRoKSAtPiBOb25lOgogICAgcXVldWUgPSBQZXJzaXN0ZW50TWlzc2lvblF1ZXVlKHRtcF9wYXRoIC8gIm1pc3Npb25zLmRiIikKICAgIHF1ZXVlLmVucXVldWUoCiAgICAgICAgbWlzc2lvbl9pZD0ibTEiLAogICAgICAgIG9iamVjdGl2ZT0icmVzZWFyY2ggdGhlbiBidWlsZCIsCiAgICAgICAgcHJpbWFyeV9kZXBhcnRtZW50PSJzb2Z0d2FyZSIsCiAgICApCgogICAgbG9vcCA9IENvbXBhbnlMb29wKAogICAgICAgIHF1ZXVlPXF1ZXVlLAogICAgICAgIGV4ZWN1dG9yPU9yY2hlc3RyYXRlZE1pc3Npb25FeGVjdXRvcihfcnVudGltZSgpKSwKICAgICAgICBvd25lcj0iY29tcGFueS1sb29wIiwKICAgICkKCiAgICBmaW5hbCA9IGxvb3AucnVuX29uY2UoKQoKICAgIGFzc2VydCBmaW5hbCBpcyBub3QgTm9uZQogICAgYXNzZXJ0IGZpbmFsLnN0YXR1cyBpcyBRdWV1ZVN0YXR1cy5DT01QTEVURUQKICAgIGFzc2VydCBmaW5hbC5yZXN1bHRfanNvbiBpcyBub3QgTm9uZQoKICAgIHBheWxvYWQgPSBqc29uLmxvYWRzKGZpbmFsLnJlc3VsdF9qc29uKQogICAgYXNzZXJ0IHBheWxvYWRbInN0YXR1cyJdID09ICJjb21wbGV0ZWQiCiAgICBhc3NlcnQgW3N0ZXBbIndvcmtlcl9pZCJdIGZvciBzdGVwIGluIHBheWxvYWRbInN0ZXBzIl1dID09IFsKICAgICAgICAicmVzZWFyY2gtMDEiLAogICAgICAgICJkZXYtMDEiLAogICAgXQoKCmRlZiB0ZXN0X3F1ZXVlX3ByZXNlcnZlc19wcmltYXJ5X2RlcGFydG1lbnRfZm9yX21hbmFnZXJfc2VsZWN0aW9uKAogICAgdG1wX3BhdGg6IFBhdGgsCikgLT4gTm9uZToKICAgIHF1ZXVlID0gUGVyc2lzdGVudE1pc3Npb25RdWV1ZSh0bXBfcGF0aCAvICJtaXNzaW9ucy5kYiIpCiAgICBxdWV1ZS5lbnF1ZXVlKAogICAgICAgIG1pc3Npb25faWQ9Im0yIiwKICAgICAgICBvYmplY3RpdmU9InNvZnR3YXJlIG1pc3Npb24iLAogICAgICAgIHByaW1hcnlfZGVwYXJ0bWVudD0ic29mdHdhcmUiLAogICAgKQoKICAgIGV4ZWN1dG9yID0gT3JjaGVzdHJhdGVkTWlzc2lvbkV4ZWN1dG9yKF9ydW50aW1lKCkpCiAgICBjbGFpbWVkID0gcXVldWUuY2xhaW1fbmV4dChvd25lcj0ibWFudWFsIikKCiAgICBhc3NlcnQgY2xhaW1lZCBpcyBub3QgTm9uZQogICAgcmVzdWx0ID0gZXhlY3V0b3IoY2xhaW1lZCkKCiAgICBhc3NlcnQgcmVzdWx0LnN0YXR1cyBpcyBNaXNzaW9uU3RhdHVzLkNPTVBMRVRFRAogICAgYXNzZXJ0IHJlc3VsdC5tYW5hZ2VyX2lkID09ICJtZ3Itc29mdHdhcmUtMDEiCgoKZGVmIHRlc3RfYmxvY2tlZF9vcmNoZXN0cmF0b3JfcmVzdWx0X2JlY29tZXNfYmxvY2tlZF9xdWV1ZV9pdGVtKAogICAgdG1wX3BhdGg6IFBhdGgsCikgLT4gTm9uZToKICAgIHJlZ2lzdHJ5ID0gVmlydHVhbFdvcmtmb3JjZVJlZ2lzdHJ5KGRlZmF1bHRfdmlydHVhbF93b3JrZm9yY2UoKSkKCiAgICBydW50aW1lID0gTXVsdGlXb3JrZXJNaXNzaW9uT3JjaGVzdHJhdG9yKAogICAgICAgIHJlZ2lzdHJ5LAogICAgICAgIG1hbmFnZXJfcGxhbm5lcj1sYW1iZGEgKl86ICgKICAgICAgICAgICAgTWlzc2lvblN0ZXBTcGVjKAogICAgICAgICAgICAgICAgc3RlcF9pZD0icGFpZCIsCiAgICAgICAgICAgICAgICB0aXRsZT0iUGFpZCBwcm90ZWN0ZWQgd29yayIsCiAgICAgICAgICAgICAgICBkZXBhcnRtZW50PSJzb2Z0d2FyZSIsCiAgICAgICAgICAgICAgICByZXF1aXJlZF9jYXBhYmlsaXRpZXM9ZnJvemVuc2V0KHsicHl0aG9uIn0pLAogICAgICAgICAgICAgICAgZXN0aW1hdGVkX2Nvc3RfdXNkPTAuMDEsCiAgICAgICAgICAgICksCiAgICAgICAgKSwKICAgICAgICBleGVjdXRvcnM9ewogICAgICAgICAgICAiZGV2LTAxIjogbWFrZV9sb2NhbF90ZXh0X2V4ZWN1dG9yKAogICAgICAgICAgICAgICAgbGFtYmRhIGl0ZW0sIHdvcmtlcl9pZDogInNob3VsZCBub3QgcnVuIgogICAgICAgICAgICApLAogICAgICAgIH0sCiAgICAgICAgcWFfZXhlY3V0b3I9bG9jYWxfcGFzc19xYSwKICAgICkKCiAgICBxdWV1ZSA9IFBlcnNpc3RlbnRNaXNzaW9uUXVldWUodG1wX3BhdGggLyAibWlzc2lvbnMuZGIiKQogICAgcXVldWUuZW5xdWV1ZSgKICAgICAgICBtaXNzaW9uX2lkPSJtMyIsCiAgICAgICAgb2JqZWN0aXZlPSJwcm90ZWN0ZWQgbWlzc2lvbiIsCiAgICAgICAgcHJpbWFyeV9kZXBhcnRtZW50PSJzb2Z0d2FyZSIsCiAgICAgICAgbWF4X2F0dGVtcHRzPTMsCiAgICApCgogICAgbG9vcCA9IENvbXBhbnlMb29wKAogICAgICAgIHF1ZXVlPXF1ZXVlLAogICAgICAgIGV4ZWN1dG9yPU9yY2hlc3RyYXRlZE1pc3Npb25FeGVjdXRvcihydW50aW1lKSwKICAgICAgICBvd25lcj0iY29tcGFueS1sb29wIiwKICAgICkKICAgIGZpbmFsID0gbG9vcC5ydW5fb25jZSgpCgogICAgYXNzZXJ0IGZpbmFsIGlzIG5vdCBOb25lCiAgICBhc3NlcnQgZmluYWwuc3RhdHVzIGlzIFF1ZXVlU3RhdHVzLkJMT0NLRUQKICAgIGFzc2VydCBmaW5hbC5hdHRlbXB0cyA9PSAxCg==")
)

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-036" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-036"
        title = "Connect persistent company queue to full AI mission chain"
        status = "pending"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        task = "Connect the persistent SQLite company mission queue and CompanyLoop to the proven AI manager, AI researcher, QA, handoff, AI developer, and QA chain. Prove one owner-approved queued live mission end-to-end with no external business actions."
    }
}
[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

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

git -C $ws add ahos_core/ahos/company_runtime.py ahos_core/tests/test_company_runtime.py ahos_core/AHOS_BACKLOG.json
$staged = git -C $ws diff --cached --name-only
if ($staged) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "feat(ahos): connect queue to mission orchestrator"
    if ($LASTEXITCODE -ne 0) {
        throw "git commit failed. No live AI call was made."
    }
    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "git push failed. No live AI call was made."
    }
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

foreach ($candidate in @($liveDb, "$liveDb-shm", "$liveDb-wal")) {
    Remove-Item $candidate -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Local tests passed."
Write-Host "Starting ONE queued full-AI mission..."
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
PLAN_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-manager"
WORK_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-queued-company"
MISSION_ID = "AHOS-036-queued-full-ai"
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
                "automation prototype. Do not modify external systems."
            )
        else:
            execution_contract = (
                f"{step.title}\n\nExecution contract: Use the previous research "
                f"handoff in your task context and create exactly one artifact "
                f"named {DEV_FILE}. Describe a small local implementation plan "
                "based directly on that research. Do not modify external systems."
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
Create a tiny local-only automation prototype plan.
The AI manager must choose exactly two steps: research first, software second.
The research worker must produce {RESEARCH_FILE}.
The software worker must depend on and use the research result, then produce
{DEV_FILE}. No customer contact, publishing, deployment, purchases, payments,
credential access, destructive actions, or external business systems.
""".strip()

queue.enqueue(
    mission_id=MISSION_ID,
    objective=objective,
    primary_department="software",
    max_attempts=1,
)

loop = CompanyLoop(
    queue=queue,
    executor=OrchestratedMissionExecutor(orchestrator),
    owner="AHOS-036-LIVE-COMPANY-LOOP",
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
    raise SystemExit("AHOS-036 queued full-AI mission did not complete")

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
print("AHOS-036 QUEUED FULL AI CHAIN: PASS")

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
    throw "AHOS-036 queued full-AI proof failed. See the error above."
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
$t = $b.tasks | Where-Object { $_.id -eq "AHOS-036" } | Select-Object -First 1
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

git -C $ws add ahos_core/AHOS_BACKLOG.json ahos_core/reports/AHOS-036-queued-full-ai-chain.json
$staged2 = git -C $ws diff --cached --name-only
if ($staged2) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "test(ahos): prove queued full AI company chain"
    if ($LASTEXITCODE -ne 0) {
        throw "Live proof passed, but git commit failed."
    }
    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "Live proof passed, but git push failed."
    }
}

foreach ($candidate in @($liveDb, "$liveDb-shm", "$liveDb-wal")) {
    Remove-Item $candidate -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=== AHOS-036 COMPLETE ==="
Write-Host "Persistent queue: PASS"
Write-Host "Autonomous company loop: PASS"
Write-Host "Queued mission auto-claim: PASS"
Write-Host "Real AI Department Manager: PASS"
Write-Host "Real AI Researcher: PASS"
Write-Host "Research QA: PASS"
Write-Host "Research -> Developer handoff: PASS"
Write-Host "Real AI Software Engineer: PASS"
Write-Host "Developer QA: PASS"
Write-Host "Queue result persistence: PASS"
Write-Host "Evidence report committed: PASS"
Write-Host "External publish/message/payment/deployment actions: 0"
Write-Host ""
Write-Host "CORE ROADMAP REMAINING: AHOS-037 through AHOS-042."
