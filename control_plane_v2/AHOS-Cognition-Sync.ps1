# AHOS bilissel senkron dongusunu ayakta tutar.
# Gorev tamamlandikca cognition profillerini artimli gunceller (episodic,
# procedural, reflection, semantic, metacognition, emotion).
#
#   .\AHOS-Cognition-Sync.ps1            # calismiyorsa baslat
#   .\AHOS-Cognition-Sync.ps1 -Status

param([switch]$Status, [int]$IntervalSeconds = 60)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Repo 'ahos_core\runtime'
$LogDir = Join-Path $Runtime 'reports'
$Log = Join-Path $LogDir 'cognition-sync.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-SyncProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'cognition_sync\.py' } |
        Select-Object -First 1
}

$proc = Get-SyncProcess
if ($Status) {
    if ($proc) { "calisiyor: pid $($proc.ProcessId)" } else { 'calismiyor' }
    exit 0
}
if ($proc) {
    "zaten calisiyor: pid $($proc.ProcessId)"
    exit 0
}

$args = @('tools\cognition_sync.py', '--interval', "$IntervalSeconds", '--log-file', $Log)
$started = Start-Process -FilePath 'python' -ArgumentList $args -WorkingDirectory $Repo `
    -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
$alive = Get-SyncProcess
if ($alive) {
    "baslatildi: pid $($alive.ProcessId) · log $Log"
} else {
    "BASLATILAMADI; log: $Log"
    exit 1
}
