# Start-AHOS-Owner-Console.ps1
# Launches the AHOS owner panel from the repository source (single source of truth).
# The owner types one line: "cizgi film departmani kur", "yazilim sirketi kur",
# "landing page yap", "durum" - the console creates departments, staffs them,
# routes work and runs the mission locally.

param(
    [int]$Port = 8765,
    [string]$HostAddress = "127.0.0.1",
    [string]$RuntimeDir = ""
)

$ErrorActionPreference = "Stop"

$ControlPlaneRoot = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ControlPlaneRoot
$AhosRoot = Join-Path $RepoRoot "ahos_core"

if (-not (Test-Path (Join-Path $AhosRoot "ahos\control_center.py"))) {
    throw "ahos_core not found under $RepoRoot"
}

$PythonCandidates = @(
    (Join-Path $ControlPlaneRoot ".venv\Scripts\python.exe"),
    (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
    "python"
)
$Python = $null
foreach ($candidate in $PythonCandidates) {
    if ($candidate -eq "python") { $Python = $candidate; break }
    if (Test-Path $candidate) { $Python = $candidate; break }
}

if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $AhosRoot "runtime"
}
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$env:PYTHONPATH = $AhosRoot
$env:PYTHONIOENCODING = "utf-8"

Write-Host "AHOS owner console"
Write-Host "  python : $Python"
Write-Host "  code   : $AhosRoot"
Write-Host "  state  : $RuntimeDir"
Write-Host "  URL    : http://${HostAddress}:$Port"
Write-Host ""

# Panel uzun omurlu bir surectir; bu betik onu on planda calistirmaz.
# AHOS-Service.ps1 sureci cagirandan bagimsiz (WMI) baslatir, saglik
# kontrolu yapar ve hemen doner; boylece komutu cagiran terminal asili kalmaz.
$Service = Join-Path $PSScriptRoot "AHOS-Service.ps1"
if (-not (Test-Path $Service)) {
    throw "AHOS-Service.ps1 not found under $PSScriptRoot"
}
& $Service -Action start -Port $Port -RuntimeDir $RuntimeDir
