$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$EnvFile = Join-Path $Root '.env.runtime'
$WorkerExe = Join-Path $Root '.venv\Scripts\miniverse-worker.exe'
$HealthExe = Join-Path $Root '.venv\Scripts\miniverse-health.exe'
$StateDir = Join-Path $Root 'runtime\state'
$WorkspaceDir = Join-Path $Root 'runtime\workspaces'
$PidFile = Join-Path $StateDir 'worker.pid'
$LauncherPidFile = Join-Path $StateDir 'worker-launcher.pid'
$RunnerFile = Join-Path $StateDir 'worker-runner.ps1'
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
    try {
        & $HealthExe --path $Heartbeat --max-age-seconds 90
    } catch {}
    exit 0
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Remove-Item $LauncherPidFile -Force -ErrorAction SilentlyContinue

$escapedRoot = $Root.Replace("'", "''")
$escapedEnv = $EnvFile.Replace("'", "''")
$escapedWorker = $WorkerExe.Replace("'", "''")
$escapedHeartbeat = $Heartbeat.Replace("'", "''")
$escapedQueue = $QueueDb.Replace("'", "''")
$escapedWorkspace = $WorkspaceDir.Replace("'", "''")
$escapedPid = $PidFile.Replace("'", "''")

$runnerLines = @(
    '$ErrorActionPreference = ''Stop'''
    "Set-Location '$escapedRoot'"
    "Get-Content '$escapedEnv' | ForEach-Object {"
    "    if (`$_ -match '^\s*#' -or `$_ -notmatch '=') { return }"
    "    `$name, `$value = `$_ -split '=', 2"
    "    [Environment]::SetEnvironmentVariable(`$name.Trim(), `$value.Trim(), 'Process')"
    "}"
    "`$env:MINIVERSE_QUEUE_DB = '$escapedQueue'"
    "`$env:MINIVERSE_WORKER_HEALTH_FILE = '$escapedHeartbeat'"
    "`$env:MINIVERSE_WORKSPACE_ROOT = '$escapedWorkspace'"
    "`$worker = Start-Process -FilePath '$escapedWorker' -ArgumentList @('run','--owner','MINIVERSE-PC') -WorkingDirectory '$escapedRoot' -PassThru"
    "`$worker.Id | Set-Content -Path '$escapedPid' -Encoding ascii"
    "`$worker.WaitForExit()"
    "exit `$worker.ExitCode"
)

$runnerLines | Set-Content -Path $RunnerFile -Encoding utf8

$launcher = Start-Process `
    -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $RunnerFile) `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

$launcher.Id | Set-Content -Path $LauncherPidFile -Encoding ascii

$deadline = (Get-Date).AddSeconds(15)
$healthy = $false

do {
    Start-Sleep -Seconds 1

    if ($launcher.HasExited) {
        break
    }

    $worker = Get-Process miniverse-worker -ErrorAction SilentlyContinue
    if ($worker) {
        try {
            & $HealthExe --path $Heartbeat --max-age-seconds 90 | Out-Host
            if ($LASTEXITCODE -eq 0) {
                $healthy = $true
                break
            }
        } catch {}
    }
} while ((Get-Date) -lt $deadline)

if (-not $healthy) {
    $worker = Get-Process miniverse-worker -ErrorAction SilentlyContinue
    if (-not $worker) {
        throw 'Miniverse worker failed to start in background.'
    }
    throw 'Miniverse worker process exists but health check did not become healthy in time.'
}

$worker = Get-Process miniverse-worker -ErrorAction SilentlyContinue | Select-Object -First 1
if ($worker) {
    $worker.Id | Set-Content -Path $PidFile -Encoding ascii
}

Write-Host "Miniverse started in background. PID $($worker.Id)"
Write-Host "Smoke mode: $env:MINIVERSE_SMOKE_MODE"
