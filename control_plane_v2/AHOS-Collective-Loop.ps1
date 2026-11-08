# AHOS kolektif koordinasyon dongusunu ayakta tutar.
# Uzman indeksi + mentor eslesmesi + engelli gorevler icin devir ONERISI uretir.
# Oneriler verified=false'dir; basari sayilmaz.

param([switch]$Status, [int]$IntervalSeconds = 300)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Repo 'ahos_core\runtime'
$LogDir = Join-Path $Runtime 'reports'
$Log = Join-Path $LogDir 'collective-loop.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-CollectiveProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'collective_loop\.py' } |
        Select-Object -First 1
}

$proc = Get-CollectiveProcess
if ($Status) {
    if ($proc) { "calisiyor: pid $($proc.ProcessId)" } else { 'calismiyor' }
    exit 0
}
if ($proc) {
    "zaten calisiyor: pid $($proc.ProcessId)"
    exit 0
}

$args = @('tools\collective_loop.py', '--interval', "$IntervalSeconds", '--log-file', $Log)
$started = Start-Process -FilePath 'python' -ArgumentList $args -WorkingDirectory $Repo `
    -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 3
$alive = Get-CollectiveProcess
if ($alive) {
    "baslatildi: pid $($alive.ProcessId) · log $Log"
} else {
    "BASLATILAMADI; log: $Log"
    exit 1
}
