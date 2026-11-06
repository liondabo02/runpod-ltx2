$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) { throw "Python venv not found: $python" }
if (-not (Test-Path (Join-Path $pkg "ahos\public_sources.py"))) {
    throw "AHOS public_sources.py not found."
}

$code = @'
from pathlib import Path
from ahos.public_sources import collect_public_opportunities
from ahos.opportunity_intake import OpportunityCandidateStore

root = Path("runtime") / "live_intake"
report = collect_public_opportunities(root)

print("=== AHOS LIVE OPPORTUNITY INTAKE ===")
for item in report.results:
    if item.error:
        print(f"{item.source_id}: ERROR -> {item.error}")
    else:
        print(f"{item.source_id}: added {item.added_count}")

print(f"TOTAL ADDED: {report.added_count}")
print(f"FAILED SOURCES: {len(report.failures)}")

store_path = root / "public_candidates.jsonl"
store = OpportunityCandidateStore(store_path)
rows = store.all()

print(f"TOTAL STORED: {len(rows)}")
print("")
print("=== LATEST CANDIDATES ===")
for row in rows[-15:]:
    print(f"[{row.source_id}] [{row.category}] {row.title}")
    print(f"  {row.item_url}")
'@

$oldPythonPath = $env:PYTHONPATH
$oldLocation = Get-Location

try {
    $env:PYTHONPATH = $pkg
    Set-Location $root
    $code | & $python -
    if ($LASTEXITCODE -ne 0) {
        throw "Live intake failed."
    }
} finally {
    $env:PYTHONPATH = $oldPythonPath
    Set-Location $oldLocation
}

Write-Host ""
Write-Host "OpenAI API calls: 0"
Write-Host "External actions: READ-ONLY HTTP GET only"
Write-Host "Applications/outreach/payments: 0"
