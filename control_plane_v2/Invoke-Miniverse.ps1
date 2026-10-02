param(
    [Parameter(Mandatory=$true)]
    [string]$Task,

    [string]$WorkspaceName = "default-task",

    [int]$MaxAttempts = 1,

    [switch]$NoWait
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$EnvFile = Join-Path $Root '.env.runtime'
$WorkerExe = Join-Path $Root '.venv\Scripts\miniverse-worker.exe'
$StartScript = Join-Path $Root 'Start-Miniverse.ps1'
$StateDir = Join-Path $Root 'runtime\state'
$WorkspaceRoot = Join-Path $Root 'runtime\workspaces'
$Workspace = Join-Path $WorkspaceRoot $WorkspaceName
$QueueDb = Join-Path $StateDir 'tasks.db'

if (-not (Test-Path $EnvFile)) { throw "Missing .env.runtime: $EnvFile" }
if (-not (Test-Path $WorkerExe)) { throw "Missing worker executable: $WorkerExe" }

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name, $value = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
}

$env:MINIVERSE_QUEUE_DB = $QueueDb
$env:MINIVERSE_WORKSPACE_ROOT = $WorkspaceRoot
$env:MINIVERSE_WORKER_HEALTH_FILE = Join-Path $StateDir 'worker-heartbeat.json'

$worker = Get-Process miniverse-worker -ErrorAction SilentlyContinue
if (-not $worker) {
    if (-not (Test-Path $StartScript)) { throw 'Miniverse worker is not running and Start-Miniverse.ps1 is missing.' }
    & $StartScript
    Start-Sleep -Seconds 2
}

$taskId = & $WorkerExe enqueue $Task --workspace $Workspace --max-attempts $MaxAttempts
Write-Host "TASK ID: $taskId"
Write-Host "Workspace: $Workspace"
Write-Host "Smoke mode: $env:MINIVERSE_SMOKE_MODE"

if ($NoWait) {
    Write-Host 'Task queued. Use Status-Miniverse.ps1 and miniverse-worker status <TASK_ID> to inspect later.'
    exit 0
}

do {
    Start-Sleep -Seconds 3
    $status = python -c "import sqlite3; c=sqlite3.connect(r'$QueueDb'); r=c.execute('SELECT status FROM tasks WHERE id=?', ('$taskId',)).fetchone(); print(r[0] if r else 'missing')"
    Write-Host "STATUS: $status"
} while ($status -eq 'pending' -or $status -eq 'running')

Write-Host "`n--- FINAL RESULT ---"
& $WorkerExe status $taskId

if ($status -ne 'completed') {
    exit 1
}
