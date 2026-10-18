# AHOS Panel 8766 — sinirli otomatik kurtarma (supervisor)
# Kurulum:  schtasks /Create /TN "AHOS-Panel-8766" /SC ONLOGON /RL LIMITED /F ^
#            /TR "powershell -NoProfile -ExecutionPolicy Bypass -File <BU_DOSYA> -Port 8766"
# Kaldirma: schtasks /Delete /TN "AHOS-Panel-8766" /F
#           Remove-Item <runtime>\panel-8766.pid, <runtime>\supervisor.log
# Not: 8765'e dokunmaz; ayni portta ikinci surec baslatmaz; en fazla 3 deneme / 10 dk.
param(
    [int]$Port = 8766,
    [int]$MaxAttempts = 3,
    [int]$WindowMinutes = 10
)

$ErrorActionPreference = "Stop"
$ControlPlane = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ControlPlane
$Runtime = Join-Path $RepoRoot "ahos_core\runtime"
$Log = Join-Path $Runtime "supervisor.log"
$Service = Join-Path $ControlPlane "AHOS-Service.ps1"

function Write-Log([string]$message) {
    New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
    ("{0} {1}" -f (Get-Date -Format o), $message) | Add-Content -Path $Log -Encoding utf8
}

function Test-Health {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/status" -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    } catch { return $false }
}

if ($Port -ne 8766) {
    Write-Log "reddedildi: yalnizca 8766 yonetilir (istenen $Port)"
    exit 2
}

if (Test-Health) {
    Write-Log "saglikli: panel zaten calisiyor, islem yok"
    exit 0
}

$started = Get-Date
$attempt = 0
while ($attempt -lt $MaxAttempts) {
    if (((Get-Date) - $started).TotalMinutes -gt $WindowMinutes) {
        Write-Log "pencere asildi ($WindowMinutes dk); vazgecildi"
        exit 3
    }
    $attempt++
    Write-Log "deneme $attempt/$MaxAttempts"
    try { & $Service -Action start -Port $Port | Out-Null } catch { Write-Log ("start hata: " + $_.Exception.Message) }
    Start-Sleep -Seconds 10
    if (Test-Health) {
        Write-Log "basarili: panel saglikli (deneme $attempt)"
        exit 0
    }
}

Write-Log "BASARISIZ: $MaxAttempts denemede saglik saglanamadi"
exit 1
