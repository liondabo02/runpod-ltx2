$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$core = Join-Path $repo "ahos_core"

Write-Host "=== STUDIO-008 FREE ACCEPTANCE PREFLIGHT ==="
$env:PYTHONPATH = $core
Push-Location $core
try {
    python -m pytest tests/test_studio_acceptance.py -q
    if ($LASTEXITCODE -ne 0) { throw "STUDIO-008 preflight tests failed" }

    $backlog = Get-Content .\STUDIO_BACKLOG.json -Raw | ConvertFrom-Json
    $unfinished = @($backlog.tasks | Where-Object { $_.id -match '^STUDIO-00[1-7]$' -and $_.status -ne 'completed' })
    if ($unfinished.Count -gt 0) {
        Write-Host "BLOCKED prerequisites: $($unfinished.id -join ', ')" -ForegroundColor Yellow
    } else {
        Write-Host "Roadmap prerequisites: PASS"
    }
}
finally {
    Pop-Location
}

Write-Host "Owner approval for paid episode: NOT GRANTED"
Write-Host "Paid execution requested: NO"
Write-Host "Render calls: 0"
Write-Host "Paid API spend: USD 0"
Write-Host "Publish actions: 0"
Write-Host "=== STUDIO-008 PREFLIGHT COMPLETE - PAID EXECUTION BLOCKED ==="
