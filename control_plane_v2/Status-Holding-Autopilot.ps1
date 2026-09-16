param(
    [decimal]$DailyBudgetUsd = 0.10,
    [decimal]$PaidTaskReserveUsd = 0.035
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$PidFile = Join-Path $StateDir 'holding-autopilot.pid'
$OutLog = Join-Path $StateDir 'holding-autopilot.out.log'
$ErrLog = Join-Path $StateDir 'holding-autopilot.err.log'
$BudgetFile = Join-Path $StateDir 'holding-autopilot-budget.json'
$ActiveTaskFile = Join-Path $StateDir 'holding-autopilot-active-task.json'

if (Test-Path $PidFile) {
    $pidValue = [int](Get-Content $PidFile -Raw)
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "AHOS AUTOPILOT: RUNNING (PID $pidValue)"
    } else {
        Write-Host 'AHOS AUTOPILOT: STOPPED (stale PID file)'
    }
} else {
    Write-Host 'AHOS AUTOPILOT: STOPPED'
}

$today = (Get-Date).ToString('yyyy-MM-dd')
$spent = [decimal]0
if (Test-Path $BudgetFile) {
    try {
        $budget = Get-Content $BudgetFile -Raw | ConvertFrom-Json
        if ($budget.date -eq $today) {
            $spent = [decimal]$budget.spent_usd
        }
    } catch {}
}

$remaining = $DailyBudgetUsd - $spent
Write-Host "AI spend today ($today): USD $spent / USD $DailyBudgetUsd"
Write-Host "Paid-task reserve: USD $PaidTaskReserveUsd"

if ($remaining -ge $PaidTaskReserveUsd) {
    Write-Host "MODE: PAID-ELIGIBLE (remaining USD $remaining)"
} else {
    Write-Host "MODE: FREE-ONLY (paid AI paused; remaining USD $remaining)"
}

if (Test-Path $ActiveTaskFile) {
    try {
        $active = Get-Content $ActiveTaskFile -Raw | ConvertFrom-Json
        Write-Host "ACTIVE BACKLOG ITEM: $($active.backlog_id)"
        Write-Host "ACTIVE QUEUE TASK: $($active.queue_task_id)"
    } catch {}
}

Write-Host "`n--- RECENT LOG ---"
if (Test-Path $OutLog) {
    Get-Content $OutLog -Tail 50
}

if (Test-Path $ErrLog) {
    $err = Get-Content $ErrLog -Tail 20
    if ($err) {
        Write-Host "`n--- RECENT ERRORS ---"
        $err
    }
}
