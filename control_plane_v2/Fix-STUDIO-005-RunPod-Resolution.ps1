$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$python = Join-Path $root ".venv\Scripts\python.exe"

$runpodPath = Join-Path $pkg "ahos\runpod_ltx2.py"
$testPath = Join-Path $pkg "tests\test_runpod_ltx2.py"
$backlogPath = Join-Path $pkg "STUDIO_BACKLOG.json"
$reportPath = Join-Path $pkg "reports\STUDIO-005-runpod-provider-upgrade.json"

Write-Host "=== STUDIO-005 RUNPOD PROVIDER RECOVERY ==="
Write-Host "Cause: 1280x720 uses height=720, which is not divisible by 32."
Write-Host "Fix: preview default -> 1024x576 (exact 16:9 and both divisible by 32)."
Write-Host "Live RunPod calls: 0"
Write-Host "Paid API spend: USD 0"
Write-Host ""

if (-not (Test-Path $python)) { throw "AHOS Python venv not found." }
if (-not (Test-Path $runpodPath)) { throw "runpod_ltx2.py not found. Run the provider upgrade script first." }
if (-not (Test-Path $testPath)) { throw "test_runpod_ltx2.py not found." }

$code = Get-Content $runpodPath -Raw
$patched = $code -replace 'width:\s*int\s*=\s*1280,\s*\r?\n\s*height:\s*int\s*=\s*720,', "width: int = 1024,`r`n        height: int = 576,"
if ($patched -eq $code -and $code -notmatch 'width:\s*int\s*=\s*1024,\s*\r?\n\s*height:\s*int\s*=\s*576,') {
    throw "Could not patch RunPod preview resolution safely."
}
[IO.File]::WriteAllText($runpodPath, $patched, [Text.UTF8Encoding]::new($false))

$tests = Get-Content $testPath -Raw
$tests = $tests -replace 'assert request\["width"\] == 1280', 'assert request["width"] == 1024'
$tests = $tests -replace 'assert request\["height"\] == 720', 'assert request["height"] == 576'
$tests = $tests -replace 'width=1279,\s*height=720', 'width=1023, height=576'
[IO.File]::WriteAllText($testPath, $tests, [Text.UTF8Encoding]::new($false))

$old = $env:PYTHONPATH
Push-Location $pkg
try {
    $env:PYTHONPATH = $pkg

    Write-Host "Running corrected RunPod provider tests..."
    & $python -m pytest tests\test_provider_registry.py tests\test_runpod_ltx2.py -q
    if ($LASTEXITCODE -ne 0) { throw "Corrected RunPod provider focused tests failed." }

    Write-Host "Running full AHOS + Studio regression suite..."
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression suite failed." }

    $patchScript = @'
import json
from pathlib import Path
p = Path("STUDIO_BACKLOG.json")
data = json.loads(p.read_text(encoding="utf-8"))
task = next((t for t in data["tasks"] if t["id"] == "STUDIO-005"), None)
if task is None:
    raise SystemExit("STUDIO-005 backlog entry missing")
base = task.get("result", "")
upgrade = (
    " Provider upgrade: AHOS now has a multi-provider media registry plus a "
    "guarded RunPod Serverless LTX-2 adapter using the existing endpoint. "
    "RunPod paid execution requires owner_approved + execution_enabled + "
    "paid_provider_enabled simultaneously; secrets remain environment-only. "
    "Preview render default is 1024x576 (exact 16:9; both dimensions divisible by 32)."
)
if "Provider upgrade:" not in base:
    task["result"] = base + upgrade
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
'@
    $tmpPatch = Join-Path $env:TEMP "studio005_backlog_patch.py"
    [IO.File]::WriteAllText($tmpPatch, $patchScript, [Text.UTF8Encoding]::new($false))
    & $python $tmpPatch
    if ($LASTEXITCODE -ne 0) { throw "STUDIO-005 backlog update failed." }
    Remove-Item $tmpPatch -Force -ErrorAction SilentlyContinue
}
finally {
    Pop-Location
    $env:PYTHONPATH = $old
}

$envRuntime = Join-Path $root ".env.runtime"
$apiKeyPresent = $false
if ($env:RUNPOD_API_KEY) {
    $apiKeyPresent = $true
} elseif (Test-Path $envRuntime) {
    $line = Get-Content $envRuntime -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*RUNPOD_API_KEY\s*=\s*\S+' } |
        Select-Object -First 1
    if ($line) { $apiKeyPresent = $true }
}

$report = @{
    studio_step = "STUDIO-005 provider upgrade"
    status = "PASS"
    endpoint_name = "miniverse-ltx2-video"
    endpoint_id = "dnwqoolyprqr69"
    provider_registry = "PASS"
    local_comfyui_provider = "AVAILABLE_AS_OPTION"
    runpod_ltx2_provider = "READY"
    preview_resolution = "1024x576"
    runpod_api_key_present = $apiKeyPresent
    paid_execution_default = "BLOCKED"
    owner_approval_gate = "PASS"
    execution_enable_gate = "PASS"
    paid_provider_gate = "PASS"
    live_runpod_calls = 0
    render_jobs_submitted = 0
    api_spend_usd = 0
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding UTF8

git -C $ws add `
    ahos_core/ahos/provider_registry.py `
    ahos_core/ahos/runpod_ltx2.py `
    ahos_core/tests/test_provider_registry.py `
    ahos_core/tests/test_runpod_ltx2.py `
    ahos_core/STUDIO_BACKLOG.json `
    ahos_core/reports/STUDIO-005-runpod-provider-upgrade.json

$staged = git -C $ws diff --cached --name-only
if ($staged -match "\.env\.runtime|media-providers\.local") {
    throw "Privacy guard failed: private config or runtime env was staged."
}

if ($staged) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" `
        commit -m "feat(studio): add guarded RunPod LTX2 provider"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}

Write-Host ""
Write-Host "=== STUDIO-005 RUNPOD PROVIDER UPGRADE COMPLETE ==="
Write-Host "Resolution validation bug fixed: PASS"
Write-Host "Preview resolution: 1024x576"
Write-Host "Existing RunPod LTX-2 endpoint registered: PASS"
Write-Host "Multi-provider media registry: PASS"
Write-Host "RunPod adapter tests: PASS"
Write-Host "Full AHOS + Studio regression: PASS"
Write-Host "Paid execution default: BLOCKED"
Write-Host "Owner + execution + paid-provider triple gate: PASS"
Write-Host "Live RunPod calls: 0"
Write-Host "Render submissions: 0"
Write-Host "API spend: USD 0"
Write-Host "RUNPOD API KEY PRESENT (value hidden):" $apiKeyPresent
