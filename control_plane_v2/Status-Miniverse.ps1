$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$HealthExe = Join-Path $Root '.venv\Scripts\miniverse-health.exe'
$StateDir = Join-Path $Root 'runtime\state'
$PidFile = Join-Path $StateDir 'worker.pid'
$Heartbeat = Join-Path $StateDir 'worker-heartbeat.json'

$processes = Get-Process miniverse-worker -ErrorAction SilentlyContinue
if (-not $processes) {
    Write-Host 'Miniverse worker is NOT running.'
    exit 1
}

Write-Host "Running PID(s): $($processes.Id -join ', ')"

if (Test-Path $PidFile) {
    Write-Host "Recorded PID: $(Get-Content $PidFile -Raw)"
}

if (Test-Path $HealthExe) {
    & $HealthExe --path $Heartbeat --max-age-seconds 90
} else {
    Write-Host "Health executable missing: $HealthExe"
}
