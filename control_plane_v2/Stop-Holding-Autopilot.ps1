$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root 'runtime\state\holding-autopilot.pid'

if (-not (Test-Path $PidFile)) {
    Write-Host 'AHOS Holding Autopilot is not running.'
    exit 0
}

$pidValue = [int](Get-Content $PidFile -Raw)
$process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $pidValue -Force
    Write-Host "AHOS Holding Autopilot stopped. PID: $pidValue"
} else {
    Write-Host 'AHOS Holding Autopilot process was already stopped.'
}
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
