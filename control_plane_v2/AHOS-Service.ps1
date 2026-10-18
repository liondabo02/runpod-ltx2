# AHOS panel servis yoneticisi (8766 varsayilan; 8765'e dokunmaz).
# Kullanim: -Action start|stop|status|restart [-Port 8766]
param(
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "status",
    [int]$Port = 8766,
    [string]$RuntimeDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$AhosRoot = Join-Path $RepoRoot "ahos_core"
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $AhosRoot "runtime" }
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$PidFile = Join-Path $RuntimeDir "panel-$Port.pid"
$LogFile = Join-Path $RuntimeDir "panel-$Port.log"
$ErrFile = Join-Path $RuntimeDir "panel-$Port.err"

function Get-ListenerPid {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    return 0
}

function Test-Health {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/status" -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    } catch { return $false }
}

switch ($Action) {
    "status" {
        $listenerPid = Get-ListenerPid
        $healthy = if ($listenerPid) { Test-Health } else { $false }
        [pscustomobject]@{
            port = $Port
            pid = $listenerPid
            healthy = $healthy
            pid_file = (Test-Path $PidFile)
            log = $LogFile
        } | ConvertTo-Json -Compress
    }
    "start" {
        $existingPid = Get-ListenerPid
        if ($existingPid) {
            "zaten calisiyor: port=$Port pid=$existingPid" | Write-Output
            exit 2
        }
        $env:PYTHONPATH = $AhosRoot
        $env:PYTHONIOENCODING = "utf-8"
        $proc = Start-Process -FilePath $Python `
            -ArgumentList @("-m", "ahos.control_center", "--runtime-dir", $RuntimeDir,
                            "--host", "127.0.0.1", "--port", $Port) `
            -WorkingDirectory $AhosRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile
        Set-Content -Path $PidFile -Value $proc.Id -Encoding ascii
        $ok = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Milliseconds 500
            if (Test-Health) { $ok = $true; break }
        }
        if (-not $ok) {
            "saglik kontrolu basarisiz; $ErrFile dosyasina bakin" | Write-Output
            exit 1
        }
        "calisiyor: port=$Port pid=$($proc.Id)" | Write-Output
    }
    "stop" {
        $listenerPid = Get-ListenerPid
        if (-not $pid) { "dinleyen surec yok: port=$Port" | Write-Output; exit 0 }
        if ($Port -eq 8765) { "8765 korunuyor: kapatma reddedildi" | Write-Output; exit 3 }
        Stop-Process -Id $listenerPid -Force
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        "durduruldu: port=$Port pid=$listenerPid" | Write-Output
    }
    "restart" {
        if ($Port -eq 8765) { "8765 korunuyor: yeniden baslatma reddedildi" | Write-Output; exit 3 }
        & $PSCommandPath -Action stop -Port $Port -RuntimeDir $RuntimeDir
        Start-Sleep -Seconds 2
        & $PSCommandPath -Action start -Port $Port -RuntimeDir $RuntimeDir
    }
}
