$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$PidFile = Join-Path $StateDir 'worker.pid'
$LauncherPidFile = Join-Path $StateDir 'worker-launcher.pid'

$workers = Get-Process miniverse-worker -ErrorAction SilentlyContinue
if ($workers) {
    $workers | Stop-Process -Force
    Write-Host "Stopped Miniverse worker PID(s): $($workers.Id -join ', ')"
} else {
    Write-Host 'No Miniverse worker process is running.'
}

if (Test-Path $LauncherPidFile) {
    try {
        $launcherPid = [int](Get-Content $LauncherPidFile -Raw)
        $launcher = Get-Process -Id $launcherPid -ErrorAction SilentlyContinue
        if ($launcher) {
            Stop-Process -Id $launcherPid -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Remove-Item $LauncherPidFile -Force -ErrorAction SilentlyContinue
