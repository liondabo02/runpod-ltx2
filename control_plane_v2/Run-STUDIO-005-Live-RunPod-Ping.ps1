$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envRuntime = Join-Path $root ".env.runtime"

$privateRoot = Join-Path $root "runtime\private\animation-studio\runpod"
$statePath = Join-Path $privateRoot "ltx2-live-ping-state.local.json"
$rawPath = Join-Path $privateRoot "ltx2-live-ping-result.local.json"
$reportPath = Join-Path $pkg "reports\STUDIO-005-runpod-live-ping.json"

$endpointId = "dnwqoolyprqr69"
$endpointName = "miniverse-ltx2-video"

Write-Host "=== STUDIO-005 LIVE RUNPOD LTX-2 PING ==="
Write-Host "This is the FIRST paid live execution test."
Write-Host "Endpoint:" $endpointName
Write-Host "Endpoint ID:" $endpointId
Write-Host "Render generation: NO"
Write-Host "Payload: { input: { ping: true } }"
Write-Host ""
Write-Host "IMPORTANT: This may wake the H100 worker and create a small RunPod charge."
Write-Host "The script is idempotent: if a job was already submitted, it resumes polling instead of submitting another."
Write-Host ""

if (-not (Test-Path $python)) { throw "AHOS Python venv not found." }
if (-not (Test-Path $pkg)) { throw "AHOS package not found." }

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $reportPath -Parent) | Out-Null

function Get-EnvValue([string]$path, [string]$name) {
    if (-not (Test-Path $path)) { return $null }
    $line = Get-Content $path -ErrorAction Stop |
        Where-Object { $_ -match "^\s*$([regex]::Escape($name))\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    $value = ($line -split "=", 2)[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

$apiKey = $env:RUNPOD_API_KEY
if (-not $apiKey) {
    $apiKey = Get-EnvValue $envRuntime "RUNPOD_API_KEY"
}
if (-not $apiKey) {
    throw "RUNPOD_API_KEY was not found in environment or .env.runtime."
}
Write-Host "RUNPOD API KEY: PRESENT (hidden)"

# Expose the secret only to the child Python process; never print it.
$previousKey = $env:RUNPOD_API_KEY
$env:RUNPOD_API_KEY = $apiKey
$env:PYTHONPATH = $pkg

$tmp = Join-Path $env:TEMP "studio005_runpod_live_ping.py"

$pyCode = @'
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from ahos.runpod_ltx2 import (
    PaidExecutionApproval,
    RunPodLTX2Config,
    RunPodLTX2Provider,
)

endpoint_id = sys.argv[1]
state_path = Path(sys.argv[2])
raw_path = Path(sys.argv[3])
report_path = Path(sys.argv[4])

state_path.parent.mkdir(parents=True, exist_ok=True)
raw_path.parent.mkdir(parents=True, exist_ok=True)
report_path.parent.mkdir(parents=True, exist_ok=True)

provider = RunPodLTX2Provider(
    RunPodLTX2Config(
        endpoint_id=endpoint_id,
        request_timeout_seconds=120.0,
    )
)

approval = PaidExecutionApproval(
    owner_approved=True,
    execution_enabled=True,
    paid_provider_enabled=True,
)

state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}

if state.get("completed") is True and state.get("health_ok") is True:
    print("EXISTING SUCCESSFUL LIVE PING FOUND: PASS")
    print("No new RunPod job submitted.")
    sys.exit(0)

job_id = state.get("job_id")

if not job_id:
    # Exactly one paid async job submission.
    result = provider.submit(
        provider.health_payload(),
        approval=approval,
        synchronous=False,
    )
    if not isinstance(result, dict):
        raise SystemExit(f"Unexpected RunPod /run response: {type(result).__name__}")

    job_id = result.get("id")
    if not job_id:
        raise SystemExit("RunPod /run response did not include job id.")

    state = {
        "endpoint_id": endpoint_id,
        "job_id": str(job_id),
        "submitted": True,
        "completed": False,
        "health_ok": False,
    }
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("LIVE PING JOB SUBMITTED:", job_id)
else:
    print("RESUMING EXISTING JOB:", job_id)
    print("No additional job submitted.")

terminal_success = {"COMPLETED", "DONE", "SUCCESS", "SUCCEEDED"}
terminal_failure = {"FAILED", "ERROR", "TIMED_OUT", "TIMEOUT", "CANCELLED", "CANCELED"}

deadline = time.time() + 900
last = None

while time.time() < deadline:
    result = provider.status(str(job_id))
    last = result
    if isinstance(result, dict):
        status = str(result.get("status", "")).upper()
    else:
        status = ""

    print("STATUS:", status or "<unknown>")

    if status in terminal_success:
        raw_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        output = result.get("output") if isinstance(result, dict) else None
        health_ok = bool(isinstance(output, dict) and output.get("ok") is True)

        # The worker ping contract returns mode=health and ComfyUI HTTP status.
        report = {
            "studio_step": "STUDIO-005 live RunPod ping",
            "status": "PASS" if health_ok else "FAIL",
            "endpoint_name": "miniverse-ltx2-video",
            "endpoint_id": endpoint_id,
            "job_id": str(job_id),
            "runpod_job_status": status,
            "health_ok": health_ok,
            "worker_mode": output.get("mode") if isinstance(output, dict) else None,
            "comfyui_http_status": output.get("comfyui_http_status") if isinstance(output, dict) else None,
            "comfyui_url": output.get("comfyui_url") if isinstance(output, dict) else None,
            "render_generated": False,
            "paid_live_execution": True,
            "secret_exposed": False,
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        state.update(
            {
                "completed": True,
                "health_ok": health_ok,
                "final_status": status,
            }
        )
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if not health_ok:
            raise SystemExit(
                "RunPod job completed but worker health output was not ok. "
                f"See {raw_path}"
            )

        print("WORKER HEALTH OUTPUT: PASS")
        print("MODE:", output.get("mode"))
        print("COMFYUI HTTP STATUS:", output.get("comfyui_http_status"))
        sys.exit(0)

    if status in terminal_failure:
        raw_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        state.update(
            {
                "completed": True,
                "health_ok": False,
                "final_status": status,
            }
        )
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise SystemExit(f"RunPod ping job ended with status {status}. See {raw_path}")

    time.sleep(5)

if last is not None:
    raw_path.write_text(
        json.dumps(last, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

raise SystemExit(
    "Polling timed out after 15 minutes. The job id was saved locally; "
    "rerunning this script will resume status polling WITHOUT submitting a new job."
)
'@

[IO.File]::WriteAllText($tmp, $pyCode, [Text.UTF8Encoding]::new($false))

try {
    Push-Location $pkg
    try {
        & $python $tmp $endpointId $statePath $rawPath $reportPath
        if ($LASTEXITCODE -ne 0) {
            throw "Live RunPod ping did not complete successfully."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    $env:PYTHONPATH = $null
    if ($null -eq $previousKey) {
        Remove-Item Env:\RUNPOD_API_KEY -ErrorAction SilentlyContinue
    } else {
        $env:RUNPOD_API_KEY = $previousKey
    }
}

if (-not (Test-Path $reportPath)) {
    throw "Expected live-ping report was not created."
}

$report = Get-Content $reportPath -Raw | ConvertFrom-Json
if (-not $report.health_ok) {
    throw "Live ping report says health check failed."
}

git -C $ws add ahos_core/reports/STUDIO-005-runpod-live-ping.json

$staged = git -C $ws diff --cached --name-only
if ($staged) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" `
        commit -m "test(studio): verify live RunPod LTX2 worker"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}

Write-Host ""
Write-Host "=== STUDIO-005 LIVE RUNPOD PING COMPLETE ==="
Write-Host "Endpoint authentication: PASS"
Write-Host "Paid RunPod job submission: PASS"
Write-Host "LTX-2 worker startup: PASS"
Write-Host "Internal ComfyUI health: PASS"
Write-Host "Render generated: NO"
Write-Host "Secret exposed: NO"
Write-Host "Evidence report committed: PASS"
Write-Host ""
Write-Host "NEXT: STUDIO-006 voice, dubbing, music, localization + skill/provider registry."
