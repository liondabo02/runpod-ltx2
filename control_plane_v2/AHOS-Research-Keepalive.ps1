# AHOS arastirma dongusunu (research_loop) ayakta tutar.
#
#   .\AHOS-Research-Keepalive.ps1            # calismiyorsa baslat, durumu yaz
#   .\AHOS-Research-Keepalive.ps1 -Status    # yalniz durum
#
# Dongu yalniz kuyruk bossa (pending <= esik) internette arastirma yapar;
# is varken bekler. Bu betik sureci oldurmez, yalnizca yoksa baslatir.

param(
    [switch]$Status,
    [int]$IntervalSeconds = 120,
    [int]$PerTick = 6,
    [int]$IdleThreshold = 10
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Repo 'ahos_core\runtime'
$LogDir = Join-Path $Runtime 'reports'
$Log = Join-Path $LogDir 'research-loop.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-ResearchProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'research_loop\.py' } |
        Select-Object -First 1
}

$proc = Get-ResearchProcess
if ($Status) {
    if ($proc) {
        "calisiyor: pid $($proc.ProcessId)"
        $state = Join-Path $Runtime 'research\state.json'
        if (Test-Path $state) { Get-Content $state -Raw -Encoding UTF8 }
    } else {
        'calismiyor'
    }
    exit 0
}

if ($proc) {
    "zaten calisiyor: pid $($proc.ProcessId)"
    exit 0
}

# Kabuk yonlendirmesi kullanma: dongu kendi log dosyasina yazar.
$loopArgs = @(
    'tools\research_loop.py',
    '--interval', "$IntervalSeconds",
    '--per-tick', "$PerTick",
    '--idle-threshold', "$IdleThreshold",
    '--log-file', $Log
)
$started = Start-Process -FilePath 'python' -ArgumentList $loopArgs -WorkingDirectory $Repo `
    -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 4
$alive = Get-ResearchProcess
if ($alive) {
    "baslatildi: pid $($alive.ProcessId) · log $Log"
} else {
    "BASLATILAMADI; log: $Log"
    exit 1
}
