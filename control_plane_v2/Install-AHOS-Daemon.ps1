#requires -Version 5.1
<#
.SYNOPSIS
  AHOS daemon'ini oturum aciliminda otomatik baslatir (Startup klasoru).

.DESCRIPTION
  Yonetici hakki veya planli gorev gerektirmez. Olusturulan .cmd dosyasi yalnizca
  AHOS-Daemon.ps1 -Action start cagirir; daemon zaten calisiyorsa ikinci surec
  baslatmaz (pid dosyasi + canlilik kontrolu).

.EXAMPLE
  .\Install-AHOS-Daemon.ps1
  .\Install-AHOS-Daemon.ps1 -Remove
#>
param(
    [switch]$Remove,
    [string]$RuntimeDir = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime',
    [int]$IntervalSeconds = 60,
    [int]$MissionsPerHour = 2,
    [int]$MissionsTotal = 6,
    [int]$NoEvidenceLimit = 3
)

$ErrorActionPreference = 'Stop'

$startup = [Environment]::GetFolderPath('Startup')
$cmdPath = Join-Path $startup 'AHOS-Daemon.cmd'
$script = Join-Path $PSScriptRoot 'AHOS-Daemon.ps1'

if ($Remove) {
    Remove-Item $cmdPath -ErrorAction SilentlyContinue
    "kaldirildi: $cmdPath"
    return
}

if (-not (Test-Path $script)) { throw "betik bulunamadi: $script" }

$body = @(
    '@echo off',
    ('powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -Action start -RuntimeDir "{1}" -IntervalSeconds {2} -MissionsPerHour {3} -MissionsTotal {4} -NoEvidenceLimit {5}' -f $script, $RuntimeDir, $IntervalSeconds, $MissionsPerHour, $MissionsTotal, $NoEvidenceLimit)
) -join "`r`n"

Set-Content -Path $cmdPath -Value $body -Encoding ascii
"kuruldu: $cmdPath"
"geri alma: .\Install-AHOS-Daemon.ps1 -Remove"
