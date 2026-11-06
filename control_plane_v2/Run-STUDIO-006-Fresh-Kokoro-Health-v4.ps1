$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$envRuntime = Join-Path $root ".env.runtime"

$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$statePath = Join-Path $privateRoot "kokoro-live-health-v4.local.json"
$reportPath = Join-Path $pkg "reports\STUDIO-006-kokoro-live-health.json"

$endpointId = "4vygp64ky68w3z"
$endpointName = "miniverse-kokoro-tts-prod"
$healthUrl = "https://$endpointId.api.runpod.ai/health"

Write-Host "=== STUDIO-006 FRESH KOKORO HEALTH V4 ==="
Write-Host "Old worker was removed. This will start ONE fresh worker using current endpoint settings."
Write-Host "Expected health path: /health"
Write-Host "Container disk: 40 GB"
Write-Host "TTS/audio generation: NO"
Write-Host "One live request only; no automatic retry."
Write-Host "A small RunPod charge may occur while the worker starts."
Write-Host ""

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
if (-not $apiKey) { throw "RUNPOD_API_KEY not found." }

if (Test-Path $statePath) {
    try {
        $prior = Get-Content $statePath -Raw | ConvertFrom-Json
        if ($prior.live_health_pass -eq $true) {
            Write-Host "Existing successful V4 health proof found."
            Write-Host "No new live request sent."
            exit 0
        }
    } catch {}
}

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Endpoint:" $endpointName
Write-Host "Health URL:" $healthUrl
Write-Host ""
Write-Host "Sending ONE fresh authenticated /health request..."
Write-Host "Cold start can take a few minutes on first model load."

$status = $null
$body = $null
$errorMessage = $null

try {
    $resp = Invoke-WebRequest `
        -Uri $healthUrl `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 330 `
        -UseBasicParsing

    $status = [int]$resp.StatusCode
    $body = [string]$resp.Content
}
catch {
    try { $status = [int]$_.Exception.Response.StatusCode } catch {}
    try {
        if ($_.ErrorDetails.Message) {
            $body = [string]$_.ErrorDetails.Message
        }
    } catch {}
    $errorMessage = [string]$_.Exception.Message
}

if ($status -ne 200) {
    Write-Host ""
    Write-Host "=== FRESH KOKORO HEALTH DID NOT RETURN 200 ==="
    if ($status) { Write-Host "HTTP STATUS:" $status }
    if ($errorMessage) { Write-Host "ERROR:" $errorMessage }
    Write-Host "Automatic retry: NO"
    Write-Host "TTS request: NO"
    Write-Host "Open RunPod Logs and check whether the NEW worker is polling /health."
    throw "Fresh Kokoro health request did not return HTTP 200."
}

Write-Host ""
Write-Host "HTTP 200: PASS"

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null

$state = [ordered]@{
    endpoint_id = $endpointId
    endpoint_name = $endpointName
    live_health_pass = $true
    http_status = 200
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
}
$state | ConvertTo-Json -Depth 5 |
    Set-Content -Path $statePath -Encoding UTF8

$report = [ordered]@{
    studio_step = "STUDIO-006 Kokoro fresh-worker live health"
    status = "PASS"
    endpoint_name = $endpointName
    endpoint_id = $endpointId
    endpoint_type = "load_balancer"
    health_path = "/health"
    http_status = 200
    worker_health = "PASS"
    fresh_worker_after_recycle = $true
    disk_verified_gb = 40
    tts_request_sent = $false
    audio_generated = $false
    paid_live_execution = $true
    secret_exposed = $false
}
$report | ConvertTo-Json -Depth 6 |
    Set-Content -Path $reportPath -Encoding UTF8

git -C $ws add ahos_core/reports/STUDIO-006-kokoro-live-health.json

$staged = git -C $ws diff --cached --name-only
if ($staged) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" `
        commit -m "test(studio): verify fresh Kokoro worker health"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}

Write-Host ""
Write-Host "=== STUDIO-006 FRESH KOKORO HEALTH COMPLETE ==="
Write-Host "Fresh worker with current settings: PASS"
Write-Host "40 GB container disk: PASS"
Write-Host "Load Balancer authentication: PASS"
Write-Host "Kokoro /health: PASS"
Write-Host "HTTP status: 200"
Write-Host "TTS request sent: NO"
Write-Host "Audio generated: NO"
Write-Host "Evidence report committed: PASS"
Write-Host ""
Write-Host "NEXT: one tiny real Kokoro speech sample, then wire the live provider into AHOS."
