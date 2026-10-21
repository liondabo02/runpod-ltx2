#requires -Version 5.1
<#
.SYNOPSIS
  Oracle'daki Ollama dugumune SSH tuneli acar ve AHOS daemon'unu modele baglar.

.DESCRIPTION
  - 11500 -> VM:11434 tuneli (yalniz localhost, port internete acilmaz)
  - /api/tags ile modelin gercekten yuklu oldugunu dogrular
  - autonomy.pause varsa kaldirir (kanit kapisi temiz baslasin)
  - daemon'u -LlmBaseUrl/-LlmFree ile yeniden baslatir
  - ahos-status ciktisini gosterir

.EXAMPLE
  .\Connect-AhosModel.ps1 -VmIp 130.61.x.x
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$VmIp,
    [string]$KeyPath = "$env:USERPROFILE\.ssh\ahos-quality-99\oracle_ed25519",
    [string]$User = 'ubuntu',
    [int]$LocalPort = 11500,
    [string]$Model = 'qwen2.5-coder:7b',
    [string]$RuntimeDir = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime',
    [switch]$KeepTunnel
)

$ErrorActionPreference = 'Stop'
$ControlPlane = $PSScriptRoot
$Root = Split-Path -Parent $ControlPlane
$PidFile = Join-Path $RuntimeDir "tunnel-$LocalPort.pid"

if (-not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH anahtari yok: $KeyPath"
}

# Eski tunel varsa kapat.
if (Test-Path $PidFile) {
    $old = Get-Content $PidFile -Raw
    if ($old) { Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "tunel aciliyor: 127.0.0.1:$LocalPort -> ${VmIp}:11434"
$tunnel = Start-Process -FilePath 'ssh' -ArgumentList @(
    '-i', $KeyPath,
    '-o', 'StrictHostKeyChecking=accept-new',
    '-o', 'ExitOnForwardFailure=yes',
    '-N',
    '-L', "${LocalPort}:localhost:11434",
    "${User}@${VmIp}"
) -WindowStyle Hidden -PassThru
Set-Content -Path $PidFile -Value $tunnel.Id -Encoding ascii

$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$LocalPort/api/tags" -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    throw "Tunel uzerinden Ollama'ya ulasilamadi. SSH anahtari/IP ve VM'de 'systemctl is-active ollama' kontrol edin."
}

$tags = (Invoke-WebRequest -Uri "http://127.0.0.1:$LocalPort/api/tags" -UseBasicParsing -TimeoutSec 10).Content | ConvertFrom-Json
$names = @($tags.models | ForEach-Object { $_.name })
Write-Host ("modeller: " + ($names -join ', '))
if ($names -notcontains $Model -and -not ($names | Where-Object { $_ -like "$Model*" })) {
    Write-Warning "istenen model ($Model) listede yok; VM'de 'ollama pull $Model' calistirin."
}

$pause = Join-Path $RuntimeDir 'autonomy.pause'
if (Test-Path $pause) { Remove-Item $pause -Force; Write-Host 'autonomy.pause kaldirildi' }

& (Join-Path $ControlPlane 'AHOS-Daemon.ps1') -Action restart `
    -RuntimeDir $RuntimeDir `
    -LlmBaseUrl "http://127.0.0.1:$LocalPort/v1" `
    -LlmModel $Model `
    -LlmFree | Out-Null

$status = Get-Content (Join-Path $RuntimeDir 'daemon-state.json') -Raw | ConvertFrom-Json
Write-Host ("daemon: pid={0} mod={1} sebep={2}" -f $status.pid, $status.executor_mode, $status.executor_reason)

if (-not $KeepTunnel) {
    Write-Host "tunel arka planda calisiyor (pid $($tunnel.Id)); kapatmak icin: Stop-Process -Id $($tunnel.Id)"
}
