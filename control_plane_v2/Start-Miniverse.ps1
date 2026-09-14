$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$EnvFile = Join-Path $Root '.env.runtime'
$WorkerExe = Join-Path $Root '.venv\Scripts\miniverse-worker.exe'
$HealthExe = Join-Path $Root '.venv\Scripts\miniverse-health.exe'
$StateDir = Join-Path $Root 'runtime\state'
$WorkspaceDir = Join-Path $Root 'runtime\workspaces'
$PidFile = Join-Path $StateDir 'worker.pid'
$OutLog = Join-Path $StateDir 'worker.out.log'
$ErrLog = Join-Path $StateDir 'worker.err.log'
$Heartbeat = Join-Path $StateDir 'worker-heartbeat.json'
$QueueDb = Join-Path $StateDir 'tasks.db'

if (-not (Test-Path $EnvFile)) { throw "Missing .env.runtime: $EnvFile" }
if (-not (Test-Path $WorkerExe)) { throw "Missing worker executable: $WorkerExe" }
if (-not (Test-Path $HealthExe)) { throw "Missing health executable: $HealthExe" }

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $WorkspaceDir | Out-Null

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name, $value = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
}

$env:MINIVERSE_QUEUE_DB = $QueueDb
$env:MINIVERSE_WORKER_HEALTH_FILE = $Heartbeat
$env:MINIVERSE_WORKSPACE_ROOT = $WorkspaceDir

$existing = Get-Process miniverse-worker -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Miniverse worker already running. PID(s): $($existing.Id -join ', ')"
    exit 0
}

$p = Start-Process `
    -FilePath $WorkerExe `
    -ArgumentList @('run', '--owner', 'MINIVERSE-PC') `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

$p.Id | Set-Content -Path $PidFile -Encoding ascii
Start-Sleep -Seconds 3

if ($p.HasExited) {
    Write-Host 'Worker exited during startup.'
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 50 }
    throw 'Miniverse worker failed to start.'
}

& $HealthExe --path $Heartbeat --max-age-seconds 90
Write-Host "Miniverse started. PID: $($p.Id)"
Write-Host "Smoke mode: $env:MINIVERSE_SMOKE_MODE"
