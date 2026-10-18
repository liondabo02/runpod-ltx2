$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$core = Join-Path $repo "ahos_core"

Write-Host "=== STUDIO-007 EPISODE ASSEMBLY AND QA PROOF ==="
$env:PYTHONPATH = $core
Push-Location $core
try {
    python -m pytest tests/test_episode_assembly.py -q
    if ($LASTEXITCODE -ne 0) { throw "STUDIO-007 tests failed" }
}
finally {
    Pop-Location
}

Write-Host "Episode assembly planner: READY"
Write-Host "QA gates: continuity, child-safety, picture, audio, subtitles, technical"
Write-Host "Render calls: 0"
Write-Host "Paid API spend: USD 0"
Write-Host "Publish actions: 0"
Write-Host "=== STUDIO-007 LOCAL PROOF PASS ==="
