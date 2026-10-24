#requires -Version 5.1
<#
.SYNOPSIS
  Safely connect local AHOS to already-owned Oracle Ollama through SSH.
.DESCRIPTION
  No exposed Ollama port; no paid provider call; never changes the active daemon.
  After a verified Ollama /api/tags response, stages model.cloud.env only.
  To activate, review staged config and use an owner-approved deployment.
#>
[CmdletBinding()]
param(
    [ValidateRange(1024,65535)][int]$Port = 11500,
    [ValidateSet('qwen2.5-coder:7b','deepseek-r1:7b')]
    [string]$Model = 'qwen2.5-coder:7b'
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$InfoFile = Join-Path $PSScriptRoot 'last-instance.json'
if (-not (Test-Path -LiteralPath $InfoFile)) { throw 'Oracle instance metadata missing' }
$Info = Get-Content -LiteralPath $InfoFile -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Info.ssh_key -or -not (Test-Path -LiteralPath $Info.ssh_key)) {
    throw 'Oracle SSH key missing; tunnel cannot be established'
}
$Dest = [string]$Info.ssh_user + '@' + [string]$Info.public_ip
$Api = "http://127.0.0.1:$Port/api/tags"

function Get-Tags {
    try {
        $result = Invoke-RestMethod -Uri $Api -TimeoutSec 2 -ErrorAction Stop
        return ,@($result.models | ForEach-Object { $_.name })
    } catch {
        return ,@()
    }
}

$names = @(Get-Tags)
$started = $null
if ($names.Count -eq 0) {
    $output = Join-Path $Repo 'ahos_core\runtime\cloud-tunnel.stdout.log'
    $errorFile = Join-Path $Repo 'ahos_core\runtime\cloud-tunnel.stderr.log'
    New-Item -ItemType Directory -Path (Split-Path $output) -Force | Out-Null
    $args = @(
        '-N','-o','BatchMode=yes',
        '-o','StrictHostKeyChecking=yes',
        '-o','ExitOnForwardFailure=yes',
        '-o','ServerAliveInterval=30',
        '-i',[string]$Info.ssh_key,
        '-L',"127.0.0.1:${Port}:127.0.0.1:11434",
        $Dest
    )
    $started = Start-Process -FilePath 'ssh.exe' -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput $output -RedirectStandardError $errorFile
    for($attempt=0; $attempt -lt 12; $attempt++) {
        Start-Sleep -Milliseconds 500
        $names = @(Get-Tags)
        if ($names.Count -gt 0) { break }
        if ($started.HasExited) { break }
    }
}
if ($names.Count -eq 0) {
    if ($started -and -not $started.HasExited) { Stop-Process -Id $started.Id -ErrorAction SilentlyContinue }
    throw 'Cloud model unavailable; existing provider and AHOS daemon remain unchanged'
}
if ($names -notcontains $Model) {
    throw "Requested model is not installed on Oracle. Loaded: $($names -join ', ')"
}
$Python = 'python'
$Stager = Join-Path $PSScriptRoot 'ahos_cloud_bridge.py'
& $Python $Stager --repo $Repo --stage --model $Model
if ($LASTEXITCODE -ne 0) { throw 'Stage failed; active config unchanged' }
Write-Output 'CLOUD_TUNNEL_READY_AND_CONFIG_STAGED'
Write-Output "Model: $Model"
Write-Output 'Current daemon was NOT restarted; no keys copied to cloud and no new spending.'
