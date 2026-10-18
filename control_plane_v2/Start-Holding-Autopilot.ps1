param(
    [decimal]$DailyBudgetUsd = 0.10,
    [decimal]$PaidTaskReserveUsd = 0.08,
    [int]$IdleSleepSeconds = 300,
    [int]$PlannerIntervalHours = 6
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$LoopScript = Join-Path $Root 'Holding-Autopilot-Loop.ps1'
$PidFile = Join-Path $StateDir 'holding-autopilot.pid'
$OutLog = Join-Path $StateDir 'holding-autopilot.out.log'
$ErrLog = Join-Path $StateDir 'holding-autopilot.err.log'

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

if (Test-Path $PidFile) {
    $oldPid = [int](Get-Content $PidFile -Raw)
    $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($old) {
        Write-Host "AHOS Holding Autopilot already running. PID: $oldPid"
        exit 0
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $LoopScript)) { throw "Missing loop script: $LoopScript" }

$args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $LoopScript,
    '-DailyBudgetUsd', [string]$DailyBudgetUsd,
    '-PaidTaskReserveUsd', [string]$PaidTaskReserveUsd,
    '-IdleSleepSeconds', [string]$IdleSleepSeconds,
    '-PlannerIntervalHours', [string]$PlannerIntervalHours
)

$p = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList $args `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

$p.Id | Set-Content -Path $PidFile -Encoding ascii
Start-Sleep -Seconds 2

if ($p.HasExited) {
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 80 }
    throw 'AHOS Holding Autopilot failed to start.'
}

Write-Host "AHOS Holding Autopilot started. PID: $($p.Id)"
Write-Host "Daily API budget: USD $DailyBudgetUsd"
Write-Host "Paid-task reserve: USD $PaidTaskReserveUsd"
Write-Host "It develops only feature/ahos-autopilot and never auto-merges main."
Write-Host "Logs: $OutLog"
