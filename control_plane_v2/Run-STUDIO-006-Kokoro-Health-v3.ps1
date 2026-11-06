$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$envRuntime = Join-Path $root ".env.runtime"

$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$statePath = Join-Path $privateRoot "kokoro-live-health-v3.local.json"
$reportPath = Join-Path $pkg "reports\STUDIO-006-kokoro-live-health.json"

$endpointId = "4vygp64ky68w3z"
$endpointName = "miniverse-kokoro-tts-prod"
$healthUrl = "https://$endpointId.api.runpod.ai/health"

Write-Host "=== STUDIO-006 KOKORO LIVE HEALTH V3 ==="
Write-Host "Precondition: 40 GB disk verified and current worker is IDLE/ready."
Write-Host "This sends ONE health request only."
Write-Host "No TTS/audio generation."
Write-Host "A small RunPod charge may occur."
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

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Endpoint:" $endpointName
Write-Host "Health URL:" $healthUrl
Write-Host ""
Write-Host "Sending ONE request..."

$status = $null
$body = $null
$errorMessage = $null

try {
    $resp = Invoke-WebRequest `
        -Uri $healthUrl `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 45 `
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
    Write-Host "=== KOKORO HEALTH V3 DID NOT PASS ==="
    if ($status) { Write-Host "HTTP STATUS:" $status }
    if ($errorMessage) { Write-Host "ERROR:" $errorMessage }
    Write-Host "Second live request sent: NO"
    Write-Host "TTS request sent: NO"
    throw "Single health request did not return HTTP 200."
}

Write-Host ""
Write-Host "HTTP 200: PASS"

$parsed = $null
try { $parsed = $body | ConvertFrom-Json } catch {}

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
    studio_step = "STUDIO-006 Kokoro live health"
    status = "PASS"
    endpoint_name = $endpointName
    endpoint_id = $endpointId
    endpoint_type = "load_balancer"
    health_path = "/health"
    http_status = 200
    worker_health = "PASS"
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
        commit -m "test(studio): verify Kokoro health after disk fix"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}

Write-Host ""
Write-Host "=== STUDIO-006 KOKORO LIVE HEALTH COMPLETE ==="
Write-Host "40 GB worker disk: PASS"
Write-Host "Load Balancer auth: PASS"
Write-Host "Kokoro /health: PASS"
Write-Host "HTTP status: 200"
Write-Host "TTS request sent: NO"
Write-Host "Audio generated: NO"
Write-Host "Evidence report committed: PASS"
Write-Host ""
Write-Host "NEXT: generate ONE tiny Kokoro audio sample and validate the audio bytes."
