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
    Write-Host "AI spend today: USD $($budget.spent_usd)"
    if ($null -ne $budget.PSObject.Properties['reserved_usd']) {
        Write-Host "AI budget reserved: USD $($budget.reserved_usd)"
    }
}

Write-Host "`n--- RECENT LOG ---"
if (Test-Path $OutLog) {
    $recent = @(Get-Content $OutLog -Tail 200)
    $statusLines = @($recent | Where-Object { $_ -match '^STATUS: ' })
    $meaningful = @($recent | Where-Object { $_ -notmatch '^STATUS: ' } | Select-Object -Last 39)
    $meaningful
    if ($statusLines.Count -gt 0) {
        Write-Host "$($statusLines[-1]) (repeated $($statusLines.Count)x in recent log)"
    }
}

if (Test-Path $ErrLog) {
    $err = @(Get-Content $ErrLog -Tail 200 | Where-Object {
        $_ -match 'AUTOPILOT ERROR|ERROR:|Traceback|Exception|RuntimeError|TypeError|failed'
    } | Select-Object -Last 20)
    if ($err) {
        Write-Host "`n--- RECENT ERRORS ---"
        $err
    }
}
