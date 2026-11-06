$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$endpointId = "dnwqoolyprqr69"
$healthUrl = "https://api.runpod.ai/v2/$endpointId/health"
$envRuntime = Join-Path $root ".env.runtime"

Write-Host "=== RUNPOD SERVERLESS CONTROL-PLANE HEALTH CHECK ==="
Write-Host "Endpoint: miniverse-ltx2-video"
Write-Host "Endpoint ID: $endpointId"
Write-Host "Job submissions: 0"
Write-Host "Render submissions: 0"
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

if (-not $apiKey) {
    throw "RUNPOD_API_KEY was not found in the current environment or .env.runtime."
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Calling standard GET /health only..."
Write-Host ""

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
}

try {
    $response = Invoke-RestMethod `
        -Uri $healthUrl `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 30
}
catch {
    $statusCode = $null
    try { $statusCode = [int]$_.Exception.Response.StatusCode } catch {}
    Write-Host "=== HEALTH CHECK FAILED ==="
    if ($statusCode) {
        Write-Host "HTTP STATUS:" $statusCode
    }
    Write-Host "ERROR:" $_.Exception.Message
    Write-Host ""
    Write-Host "No RunPod job was submitted."
    exit 2
}

Write-Host "=== RUNPOD HEALTH CHECK PASS ==="
Write-Host "Authentication: PASS"
Write-Host "Endpoint health API: PASS"

if ($response.workers) {
    $w = $response.workers
    foreach ($name in @("idle","ready","running","initializing","throttled")) {
        if ($null -ne $w.$name) {
            Write-Host ("WORKERS {0}: {1}" -f $name.ToUpper(), $w.$name)
        }
    }
}

if ($response.jobs) {
    $j = $response.jobs
    foreach ($name in @("completed","failed","inProgress","inQueue","retried")) {
        if ($null -ne $j.$name) {
            Write-Host ("JOBS {0}: {1}" -f $name.ToUpper(), $j.$name)
        }
    }
}

Write-Host ""
Write-Host "RAW HEALTH SUMMARY:"
$response | ConvertTo-Json -Depth 8

Write-Host ""
Write-Host "Job submissions: 0"
Write-Host "Render submissions: 0"
Write-Host "No secret value was printed."
Write-Host "NEXT: one owner-approved ping job through the existing LTX-2 worker."
