#requires -Version 5.1
<#
.SYNOPSIS
  AHOS bekcisini oturum aciliminda baslatir (Startup klasoru).

.DESCRIPTION
  AHOS-Daemon.cmd ile birlikte calisir: biri daemon'i baslatir, digeri daemon
  olurse yeniden baslatir. Yonetici hakki veya planli gorev gerektirmez.

.EXAMPLE
  .\Install-AHOS-Watchdog.ps1
  .\Install-AHOS-Watchdog.ps1 -Remove
#>
param(
    [switch]$Remove,
    [string]$RuntimeDir = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime',
    [int]$IntervalSeconds = 60
)

$ErrorActionPreference = 'Stop'

$startup = [Environment]::GetFolderPath('Startup')
$cmdPath = Join-Path $startup 'AHOS-Watchdog.cmd'
$script = Join-Path $PSScriptRoot 'AHOS-Watchdog.ps1'

if ($Remove) {
    Remove-Item $cmdPath -ErrorAction SilentlyContinue
    "kaldirildi: $cmdPath"
    return
}

if (-not (Test-Path $script)) { throw "betik bulunamadi: $script" }

$body = @(
    '@echo off',
    ('powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -RuntimeDir "{1}" -IntervalSeconds {2}' -f $script, $RuntimeDir, $IntervalSeconds)
) -join "`r`n"

Set-Content -Path $cmdPath -Value $body -Encoding ascii
"kuruldu: $cmdPath"
"geri alma: .\Install-AHOS-Watchdog.ps1 -Remove"
