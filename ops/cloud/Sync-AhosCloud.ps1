#requires -Version 5.1
<#
.SYNOPSIS
  Bulut işçisiyle senkron: projeyi yukarı gönder, üretilen yamaları aşağı al, doğrulayıp uygula.

.DESCRIPTION
  PC kapalıyken VM saatlik olarak yama üretir (~/ahos/outbox). Bu betik:
    1. yerel projeyi VM'e kopyalar (~/ahos/project),
    2. görev listesini gönderir (varsayılan ops/cloud/tasks.sample.json),
    3. outbox'ı indirir,
    4. -Apply verilirse `python -m ahos.outbox` ile doğrulayıp uygular.

.EXAMPLE
  .\Sync-AhosCloud.ps1 -Apply
#>
param(
    [string]$VmIp = '130.61.35.81',
    [string]$KeyPath = "$env:USERPROFILE\.ssh\ahos-quality-99\oracle_ed25519",
    [string]$User = 'ubuntu',
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$ProjectPath = '',
    [string]$TasksFile = '',
    [switch]$Apply,
    [string]$VerifyCommand = 'python tools/check_offline.py'
)

$ErrorActionPreference = 'Stop'
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'ahos_core\runtime\projects\mipiluna' }
if (-not $TasksFile) { $TasksFile = Join-Path $RepoRoot 'ops\cloud\tasks.sample.json' }
$OutboxLocal = Join-Path $env:TEMP 'ahos-outbox'
$SshArgs = @('-i', $KeyPath, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new')
$Target = "$User@$VmIp"

Write-Host "1/3 proje gönderiliyor…"
& scp @SshArgs -r (Join-Path $ProjectPath 'www') "${Target}:~/ahos/project/" | Out-Null
& scp @SshArgs $TasksFile "${Target}:~/ahos/tasks.json" | Out-Null

Write-Host "2/3 outbox indiriliyor…"
if (Test-Path $OutboxLocal) { Remove-Item $OutboxLocal -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutboxLocal | Out-Null
& scp @SshArgs -r "${Target}:~/ahos/outbox/." $OutboxLocal | Out-Null
$proposals = @(Get-ChildItem $OutboxLocal -Filter '*.json' -ErrorAction SilentlyContinue)
Write-Host "   öneri sayısı: $($proposals.Count)"
if ($proposals.Count -eq 0) { Write-Host 'yeni öneri yok'; return }

if (-not $Apply) {
    Write-Host "3/3 uygulanmadı (-Apply verilmedi). Öneriler: $OutboxLocal"
    return
}

Write-Host "3/3 doğrulanıp uygulanıyor…"
Push-Location (Join-Path $RepoRoot 'ahos_core')
try {
    & python -m ahos.outbox --dir $OutboxLocal --root $ProjectPath --verify $VerifyCommand `
        --stop-file (Join-Path $RepoRoot 'ahos_core\runtime\autonomy.stop') `
        --report (Join-Path $RepoRoot 'quality\evidence\cloud-outbox-results.jsonl')
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
