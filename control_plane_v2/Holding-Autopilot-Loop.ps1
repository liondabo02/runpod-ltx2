param(
    [decimal]$DailyBudgetUsd = 0.10,
    [int]$IdleSleepSeconds = 300,
    [int]$PlannerIntervalHours = 6
)

$ErrorActionPreference = 'Stop'

$ControlRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ControlRoot
$EnvFile = Join-Path $ControlRoot '.env.runtime'
$WorkerExe = Join-Path $ControlRoot '.venv\Scripts\miniverse-worker.exe'
$PythonExe = Join-Path $ControlRoot '.venv\Scripts\python.exe'
$StartWorker = Join-Path $ControlRoot 'Start-Miniverse.ps1'
$StateDir = Join-Path $ControlRoot 'runtime\state'
$WorkspaceRoot = Join-Path $ControlRoot 'runtime\workspaces'
$Workspace = Join-Path $WorkspaceRoot 'ahos-autopilot'
$QueueDb = Join-Path $StateDir 'tasks.db'
$BudgetFile = Join-Path $StateDir 'holding-autopilot-budget.json'
$PlannerStamp = Join-Path $StateDir 'holding-autopilot-planner.txt'
$Branch = 'feature/ahos-autopilot'

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $WorkspaceRoot | Out-Null

if (-not (Test-Path $EnvFile)) { throw "Missing .env.runtime: $EnvFile" }
if (-not (Test-Path $WorkerExe)) { throw "Missing worker executable: $WorkerExe" }
if (-not (Test-Path $PythonExe)) { throw "Missing venv Python: $PythonExe" }

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name, $value = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
}

$env:MINIVERSE_QUEUE_DB = $QueueDb
$env:MINIVERSE_WORKSPACE_ROOT = $WorkspaceRoot
$env:MINIVERSE_WORKER_HEALTH_FILE = Join-Path $StateDir 'worker-heartbeat.json'

if (-not (Get-Process miniverse-worker -ErrorAction SilentlyContinue)) {
    & $StartWorker
    Start-Sleep -Seconds 2
}

& git -C $RepoRoot fetch origin --prune | Out-Host
if (-not (Test-Path (Join-Path $Workspace '.git'))) {
    & git -C $RepoRoot worktree add -B $Branch $Workspace "origin/$Branch" | Out-Host
} else {
    $dirty = & git -C $Workspace status --porcelain
    if ($dirty) {
        throw "AHOS worktree contains uncommitted changes. Refusing to overwrite: $Workspace"
    }
    & git -C $Workspace reset --hard "origin/$Branch" | Out-Host
}

function Get-BudgetState {
    $today = (Get-Date).ToString('yyyy-MM-dd')
    if (Test-Path $BudgetFile) {
        $state = Get-Content $BudgetFile -Raw | ConvertFrom-Json
        if ($state.date -eq $today) { return $state }
    }
    return [pscustomobject]@{ date = $today; spent_usd = 0.0 }
}

function Save-BudgetState($state) {
    $state | ConvertTo-Json | Set-Content -Path $BudgetFile -Encoding utf8
}

function Add-Cost([decimal]$amount) {
    $state = Get-BudgetState
    $state.spent_usd = [double]$state.spent_usd + [double]$amount
    Save-BudgetState $state
}

function Invoke-AhosTask([string]$instruction) {
    $taskId = & $WorkerExe enqueue $instruction --workspace $Workspace --max-attempts 1
    Write-Host "AHOS TASK: $taskId"
    do {
        Start-Sleep -Seconds 5
        $record = (& $WorkerExe status $taskId | Out-String) | ConvertFrom-Json
        Write-Host "STATUS: $($record.status)"
    } while ($record.status -eq 'pending' -or $record.status -eq 'running')

    if ($record.result -and $record.result.builder -and $record.result.builder.estimated_cost_usd) {
        Add-Cost ([decimal]$record.result.builder.estimated_cost_usd)
    }
    return $record
}

function Test-AhosCore {
    Push-Location $Workspace
    try {
        $oldPyPath = $env:PYTHONPATH
        $env:PYTHONPATH = Join-Path $Workspace 'ahos_core'
        & $PythonExe -m pytest ahos_core\tests -q
        return ($LASTEXITCODE -eq 0)
    } finally {
        $env:PYTHONPATH = $oldPyPath
        Pop-Location
    }
}

function Save-Backlog($doc) {
    $path = Join-Path $Workspace 'ahos_core\AHOS_BACKLOG.json'
    $doc | ConvertTo-Json -Depth 12 | Set-Content -Path $path -Encoding utf8
}

function Commit-And-Push([string]$message) {
    & git -C $Workspace add ahos_core | Out-Host
    & git -C $Workspace diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { return }
    & git -C $Workspace -c user.name='Miniverse Autopilot' -c user.email='miniverse@local.invalid' commit -m $message | Out-Host
    & git -C $Workspace push origin "HEAD:$Branch" | Out-Host
}

function Mark-Task([string]$id, [string]$status, [string]$note = '') {
    $backlogPath = Join-Path $Workspace 'ahos_core\AHOS_BACKLOG.json'
    $doc = Get-Content $backlogPath -Raw | ConvertFrom-Json
    $item = $doc.tasks | Where-Object { $_.id -eq $id } | Select-Object -First 1
    if ($null -eq $item) { return }
    $item.status = $status
    if ($status -eq 'completed') {
        $item | Add-Member -NotePropertyName completed_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o')) -Force
    }
    if ($note) {
        $item | Add-Member -NotePropertyName note -NotePropertyValue $note -Force
    }
    Save-Backlog $doc
}

function Planner-Is-Due {
    if (-not (Test-Path $PlannerStamp)) { return $true }
    $raw = Get-Content $PlannerStamp -Raw
    $last = [datetime]::Parse($raw)
    return ((Get-Date).ToUniversalTime() - $last.ToUniversalTime()).TotalHours -ge $PlannerIntervalHours
}

Write-Host "AHOS AUTOPILOT ONLINE"
Write-Host "Branch: $Branch"
Write-Host "Workspace: $Workspace"
Write-Host "Daily API budget: USD $DailyBudgetUsd"
Write-Host "Smoke mode: $env:MINIVERSE_SMOKE_MODE"

while ($true) {
    try {
        $budget = Get-BudgetState
        if ([decimal]$budget.spent_usd -ge $DailyBudgetUsd) {
            Write-Host "Daily AI budget reached: USD $($budget.spent_usd). Waiting."
            Start-Sleep -Seconds $IdleSleepSeconds
            continue
        }

        $dirty = & git -C $Workspace status --porcelain
        if ($dirty) {
            Write-Host 'Worktree is dirty; autopilot will not overwrite uncommitted work.'
            Start-Sleep -Seconds $IdleSleepSeconds
            continue
        }

        & git -C $RepoRoot fetch origin --prune | Out-Null
        & git -C $Workspace reset --hard "origin/$Branch" | Out-Null
        $backlogPath = Join-Path $Workspace 'ahos_core\AHOS_BACKLOG.json'
        $doc = Get-Content $backlogPath -Raw | ConvertFrom-Json
        $next = $doc.tasks | Where-Object {
            $_.status -eq 'pending' -and
            $_.risk -eq 'low' -and
            $_.authority -eq 'B' -and
            -not $_.requires_owner_approval
        } | Select-Object -First 1

        if ($null -eq $next) {
            if (Planner-Is-Due) {
                $planner = @'
Inspect ahos_core and AHOS_BACKLOG.json. If there are no safe pending development tasks, append at most three concrete low-risk Authority-B tasks that improve local reliability, tests, architecture, observability, or developer ergonomics. Keep IDs unique. Stay strictly inside the isolated ahos_core worktree and preserve the existing governance boundary. Use neutral local-development wording in task titles and descriptions. Modify only ahos_core/AHOS_BACKLOG.json and validate that it remains valid JSON.
'@
                $result = Invoke-AhosTask $planner
                (Get-Date).ToUniversalTime().ToString('o') | Set-Content $PlannerStamp -Encoding ascii
                if ($result.status -eq 'completed') {
                    Commit-And-Push 'autopilot: refresh safe AHOS backlog'
                } else {
                    & git -C $Workspace restore --worktree --staged . | Out-Null
                }
            }
            Start-Sleep -Seconds $IdleSleepSeconds
            continue
        }

        $taskId = [string]$next.id
        $title = [string]$next.title
        $instruction = @"
You are developing AHOS, the Autonomous Holding Operating System, in its isolated Git worktree.

Implement backlog item ${taskId}: $title

$($next.task)

Hard boundaries:
- Work only inside ahos_core.
- Stay within existing Authority A/B and the isolated worktree.
- Preserve governance and owner-approval requirements exactly.
- Do not modify AHOS_BACKLOG.json; the controller owns backlog status.
- Inspect existing code first, make the smallest coherent reversible change, and run relevant tests.
"@

        Write-Host "Starting $taskId - $title"
        $result = Invoke-AhosTask $instruction

        if ($result.status -ne 'completed') {
            & git -C $Workspace restore --worktree --staged . | Out-Null
            Mark-Task $taskId 'blocked' ([string]$result.last_error)
            Commit-And-Push "autopilot: mark $taskId blocked"
            Start-Sleep -Seconds 30
            continue
        }

        if (-not (Test-AhosCore)) {
            & git -C $Workspace restore --worktree --staged . | Out-Null
            Mark-Task $taskId 'blocked' 'AHOS test suite failed after autonomous change.'
            Commit-And-Push "autopilot: mark $taskId blocked after test failure"
            Start-Sleep -Seconds 30
            continue
        }

        Mark-Task $taskId 'completed'
        Commit-And-Push "autopilot: complete $taskId $title"
        Write-Host "COMPLETED: $taskId"
        Start-Sleep -Seconds 30
    } catch {
        Write-Host "AUTOPILOT ERROR: $($_.Exception.Message)"
        Start-Sleep -Seconds $IdleSleepSeconds
    }
}
