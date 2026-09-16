$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$EnvFile = Join-Path $Root '.env.runtime'
$WorkerExe = Join-Path $Root '.venv\Scripts\miniverse-worker.exe'
$StateDir = Join-Path $Root 'runtime\state'
$WorkspaceDir = Join-Path $Root 'runtime\workspaces'
$PidFile = Join-Path $StateDir 'worker.pid'
$LauncherPidFile = Join-Path $StateDir 'worker-launcher.pid'
$RunnerFile = Join-Path $StateDir 'worker-runner.ps1'
$Heartbeat = Join-Path $StateDir 'worker-heartbeat.json'
$QueueDb = Join-Path $StateDir 'tasks.db'

if (-not (Test-Path $EnvFile)) { throw "Missing .env.runtime: $EnvFile" }
if (-not (Test-Path $WorkerExe)) { throw "Missing worker executable: $WorkerExe" }

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $WorkspaceDir | Out-Null

function Test-HeartbeatFresh {
    if (-not (Test-Path $Heartbeat)) { return $false }
    try {
        $h = Get-Content $Heartbeat -Raw | ConvertFrom-Json
        if ($h.state -notin @('polling','running')) { return $false }
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
        $age = $now - [double]$h.timestamp
        return ($age -ge 0 -and $age -le 60)
    } catch {
        return $false
    }
}

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name,$value = $_ -split '=',2
    [Environment]::SetEnvironmentVariable($name.Trim(),$value.Trim(),'Process')
}

$env:MINIVERSE_QUEUE_DB = $QueueDb
$env:MINIVERSE_WORKER_HEALTH_FILE = $Heartbeat
$env:MINIVERSE_WORKSPACE_ROOT = $WorkspaceDir

$existing = Get-Process miniverse-worker -ErrorAction SilentlyContinue
if ($existing) {
    if (Test-HeartbeatFresh) {
        Write-Host "Miniverse worker already running and healthy. PID(s): $($existing.Id -join ', ')"
        exit 0
    }
    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Seconds 2
        if (Test-HeartbeatFresh) {
            Write-Host "Miniverse worker became healthy. PID(s): $($existing.Id -join ', ')"
            exit 0
        }
        $existing = Get-Process miniverse-worker -ErrorAction SilentlyContinue
        if (-not $existing) { break }
    } while ((Get-Date) -lt $deadline)

    if ($existing) { throw 'Worker exists but heartbeat did not become healthy within 90 seconds.' }
}

$runner = @"
`$ErrorActionPreference = 'Stop'
Set-Location '$($Root.Replace("'","''"))'
Get-Content '$($EnvFile.Replace("'","''"))' | ForEach-Object {
    if (`$_ -match '^\s*#' -or `$_ -notmatch '=') { return }
    `$name,`$value = `$_ -split '=',2
    [Environment]::SetEnvironmentVariable(`$name.Trim(),`$value.Trim(),'Process')
}
`$env:MINIVERSE_QUEUE_DB = '$($QueueDb.Replace("'","''"))'
`$env:MINIVERSE_WORKER_HEALTH_FILE = '$($Heartbeat.Replace("'","''"))'
`$env:MINIVERSE_WORKSPACE_ROOT = '$($WorkspaceDir.Replace("'","''"))'
`$env:OPENHANDS_SUPPRESS_BANNER = '1'
& '$($WorkerExe.Replace("'","''"))' run --owner MINIVERSE-PC
"@

Set-Content -Path $RunnerFile -Value $runner -Encoding utf8

$launcher = Start-Process `
    -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',$RunnerFile) `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

$launcher.Id | Set-Content -Path $LauncherPidFile -Encoding ascii

$deadline = (Get-Date).AddSeconds(90)
do {
    Start-Sleep -Seconds 2
    $worker = Get-Process miniverse-worker -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($worker -and (Test-HeartbeatFresh)) {
        $worker.Id | Set-Content -Path $PidFile -Encoding ascii
        Write-Host "Miniverse started hidden in background. PID $($worker.Id)"
        exit 0
    }
    if ($launcher.HasExited) {
        throw "Hidden launcher exited during startup with code $($launcher.ExitCode)."
    }
} while ((Get-Date) -lt $deadline)

throw 'Miniverse worker did not become healthy within 90 seconds.'
