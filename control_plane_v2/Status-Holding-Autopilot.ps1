$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$PidFile = Join-Path $StateDir 'holding-autopilot.pid'
$OutLog = Join-Path $StateDir 'holding-autopilot.out.log'
$ErrLog = Join-Path $StateDir 'holding-autopilot.err.log'
$BudgetFile = Join-Path $StateDir 'holding-autopilot-budget.json'

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

if (Test-Path $BudgetFile) {
    $budget = Get-Content $BudgetFile -Raw | ConvertFrom-Json
    $spent = [decimal]$budget.spent_usd
    $limit = if ($null -ne $budget.daily_limit_usd) { [decimal]$budget.daily_limit_usd } else { [decimal]0.10 }
    $reserve = if ($null -ne $budget.paid_task_reserve_usd) { [decimal]$budget.paid_task_reserve_usd } else { [decimal]0.035 }
    $remaining = $limit - $spent

    Write-Host "AI spend today: USD $spent / USD $limit"
    Write-Host "Paid-task reserve: USD $reserve"
    if ($remaining -lt $reserve) {
        Write-Host "MODE: FREE-ONLY (paid AI paused; remaining USD $remaining)"
    } else {
        Write-Host "MODE: FREE-FIRST + PAID AI AVAILABLE (remaining USD $remaining)"
    }
}

Write-Host "`n--- RECENT LOG ---"
if (Test-Path $OutLog) { Get-Content $OutLog -Tail 40 }

if (Test-Path $ErrLog) {
    $err = Get-Content $ErrLog -Tail 20
    if ($err) {
        Write-Host "`n--- RECENT ERRORS ---"
        $err
    }
}
