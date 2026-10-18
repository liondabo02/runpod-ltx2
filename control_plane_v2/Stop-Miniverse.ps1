$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$PidFile = Join-Path $Root 'runtime\state\worker.pid'
$stopped = @()

if (Test-Path $PidFile) {
    $pidText = (Get-Content $PidFile -Raw).Trim()
    if ($pidText -match '^\d+$') {
        $pidValue = [int]$pidText
        $p = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $pidValue -Force
            $stopped += $pidValue
        }
    }
}

Get-Process miniverse-worker -ErrorAction SilentlyContinue | ForEach-Object {
    if ($stopped -notcontains $_.Id) {
        Stop-Process -Id $_.Id -Force
        $stopped += $_.Id
    }
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

if ($stopped.Count -gt 0) {
    Write-Host "Miniverse stopped. PID(s): $($stopped -join ', ')"
} else {
    Write-Host 'Miniverse was already stopped.'
}
