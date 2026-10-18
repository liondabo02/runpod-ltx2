param(
    [decimal]$DailyBudgetUsd = 0.10,
    [decimal]$PaidTaskReserveUsd = 0.035,
    [decimal]$TaskHardCapUsd = 0.03
)

$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path

if (-not (Test-Path (Join-Path $Root 'miniverse\config.py'))) {
    throw "Run this script from control_plane_v2. Current path: $Root"
}

Write-Host "=== AHOS SAFETY FIXES V2 ==="
Write-Host "Daily budget: USD $DailyBudgetUsd"
Write-Host "Per-task hard cap: USD $TaskHardCapUsd"
Write-Host "Paid-task reserve: USD $PaidTaskReserveUsd"

# Keep paid work stopped while patching.
if (Test-Path ".\Stop-Holding-Autopilot.ps1") {
    try {
        & ".\Stop-Holding-Autopilot.ps1"
    } catch {
        Write-Host "Autopilot stop warning: $($_.Exception.Message)"
    }
}

# 1) Python config: add a per-run hard cap setting.
$configPath = Join-Path $Root 'miniverse\config.py'
$config = Get-Content $configPath -Raw

if ($config -notmatch 'max_budget_per_run_usd') {
    $needle = '    smoke_mode: bool = _env_flag("MINIVERSE_SMOKE_MODE", False)'
    $replacement = @"
    smoke_mode: bool = _env_flag("MINIVERSE_SMOKE_MODE", False)
    max_budget_per_run_usd: float = float(
        os.getenv("MINIVERSE_MAX_BUDGET_PER_RUN_USD", "0.03")
    )
"@
    if (-not $config.Contains($needle)) {
        throw "Could not patch config.py: smoke_mode line not found."
    }
    $config = $config.Replace($needle, $replacement.TrimEnd())
}
Set-Content -Path $configPath -Value $config -Encoding utf8

# 2) OpenHands builder: enforce SDK max_budget_per_run.
$builderPath = Join-Path $Root 'miniverse\openhands_builder.py'
$builder = Get-Content $builderPath -Raw

if ($builder -notmatch 'max_budget_per_run=self\.settings\.max_budget_per_run_usd') {
    $needle = '        conversation = Conversation(agent=agent, workspace=str(workspace_path))'
    $replacement = @"
        conversation = Conversation(
            agent=agent,
            workspace=str(workspace_path),
            max_budget_per_run=self.settings.max_budget_per_run_usd,
        )
"@
    if (-not $builder.Contains($needle)) {
        throw "Could not patch openhands_builder.py: Conversation constructor not found."
    }
    $builder = $builder.Replace($needle, $replacement.TrimEnd())
}
Set-Content -Path $builderPath -Value $builder -Encoding utf8

# 3) Replace the controller with a free-first, restart-safe, date-aware loop.
$loopPath = Join-Path $Root 'Holding-Autopilot-Loop.ps1'
$loop = @'
param(
    [decimal]$DailyBudgetUsd = 0.10,
    [decimal]$PaidTaskReserveUsd = 0.035,
    [int]$IdleSleepSeconds = 300,
    [int]$PlannerIntervalHours = 6,
    [int]$FreeMaintenanceIntervalMinutes = 30
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
$MaintenanceStamp = Join-Path $StateDir 'holding-autopilot-maintenance.txt'
$ActiveTaskFile = Join-Path $StateDir 'holding-autopilot-active-task.json'
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

if (-not $env:MINIVERSE_MAX_BUDGET_PER_RUN_USD) {
    $env:MINIVERSE_MAX_BUDGET_PER_RUN_USD = '0.03'
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

function New-BudgetState {
    [pscustomobject]@{
        date = (Get-Date).ToString('yyyy-MM-dd')
        spent_usd = 0.0
    }
}

function Save-BudgetState($state) {
    $state | ConvertTo-Json | Set-Content -Path $BudgetFile -Encoding utf8
}

function Get-BudgetState {
    $today = (Get-Date).ToString('yyyy-MM-dd')
    if (Test-Path $BudgetFile) {
        try {
            $state = Get-Content $BudgetFile -Raw | ConvertFrom-Json
            if ($state.date -eq $today) {
                return $state
            }
        } catch {}
    }

    $state = New-BudgetState
    Save-BudgetState $state
    Write-Host "BUDGET RESET: $today -> USD 0"
    return $state
}

function Add-Cost([decimal]$amount) {
    if ($amount -lt 0) { return }
    $state = Get-BudgetState
    $state.spent_usd = [double]$state.spent_usd + [double]$amount
    Save-BudgetState $state
}

function Paid-Budget-Available {
    $state = Get-BudgetState
    return ([decimal]$state.spent_usd + $PaidTaskReserveUsd -le $DailyBudgetUsd)
}

function Get-RemainingBudget {
    $state = Get-BudgetState
    return ([decimal]$DailyBudgetUsd - [decimal]$state.spent_usd)
}

function Get-TaskRecord([string]$taskId) {
    try {
        return ((& $WorkerExe status $taskId | Out-String) | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Save-ActiveTask([string]$backlogId, [string]$queueTaskId) {
    [pscustomobject]@{
        backlog_id = $backlogId
        queue_task_id = $queueTaskId
        saved_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json | Set-Content -Path $ActiveTaskFile -Encoding utf8
}

function Load-ActiveTask {
    if (-not (Test-Path $ActiveTaskFile)) { return $null }
    try {
        return Get-Content $ActiveTaskFile -Raw | ConvertFrom-Json
    } catch {
        Remove-Item $ActiveTaskFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Clear-ActiveTask {
    Remove-Item $ActiveTaskFile -Force -ErrorAction SilentlyContinue
}

function Invoke-AhosTask([string]$backlogId, [string]$instruction) {
    $active = Load-ActiveTask
    $taskId = $null

    if ($active -and $active.backlog_id -eq $backlogId) {
        $existing = Get-TaskRecord ([string]$active.queue_task_id)
        if ($existing -and $existing.status -in @('pending', 'running', 'completed', 'failed')) {
            $taskId = [string]$active.queue_task_id
            Write-Host "RESUME EXISTING TASK: $backlogId -> $taskId ($($existing.status))"
        } else {
            Clear-ActiveTask
        }
    } elseif ($active) {
        $existing = Get-TaskRecord ([string]$active.queue_task_id)
        if ($existing -and $existing.status -in @('pending', 'running')) {
            throw "Another AHOS task is still active: $($active.backlog_id) / $($active.queue_task_id)"
        }
        Clear-ActiveTask
    }

    if (-not $taskId) {
        $taskId = (& $WorkerExe enqueue $instruction --workspace $Workspace --max-attempts 1).Trim()
        Save-ActiveTask $backlogId $taskId
        Write-Host "AHOS TASK: $taskId"
    }

    do {
        Start-Sleep -Seconds 5
        $record = Get-TaskRecord $taskId
        if ($null -eq $record) {
            throw "Could not read task status: $taskId"
        }
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

function Maintenance-Is-Due {
    if (-not (Test-Path $MaintenanceStamp)) { return $true }
    try {
        $last = [datetime]::Parse((Get-Content $MaintenanceStamp -Raw))
        return ((Get-Date).ToUniversalTime() - $last.ToUniversalTime()).TotalMinutes -ge $FreeMaintenanceIntervalMinutes
    } catch {
        return $true
    }
}

function Invoke-FreeMaintenance {
    if (-not (Maintenance-Is-Due)) { return }

    Write-Host 'FREE MAINTENANCE: running local checks (no AI API calls).'
    $ok = Test-AhosCore
    if ($ok) {
        Write-Host 'FREE MAINTENANCE: PASS'
    } else {
        Write-Host 'FREE MAINTENANCE: TEST FAILURE'
    }

    $status = & git -C $Workspace status --porcelain
    if ($status) {
        Write-Host 'FREE MAINTENANCE: worktree has changes; autonomous paid work will stay paused.'
    }

    (Get-Date).ToUniversalTime().ToString('o') | Set-Content $MaintenanceStamp -Encoding ascii
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
    try {
        $last = [datetime]::Parse((Get-Content $PlannerStamp -Raw))
        return ((Get-Date).ToUniversalTime() - $last.ToUniversalTime()).TotalHours -ge $PlannerIntervalHours
    } catch {
        return $true
    }
}

Write-Host 'AHOS AUTOPILOT ONLINE'
Write-Host "Branch: $Branch"
Write-Host "Workspace: $Workspace"
Write-Host "Daily API budget: USD $DailyBudgetUsd"
Write-Host "Paid-task reserve: USD $PaidTaskReserveUsd"
Write-Host "Per-task SDK hard cap: USD $env:MINIVERSE_MAX_BUDGET_PER_RUN_USD"
Write-Host 'Routing: FREE deterministic checks first -> OpenAI coding only when budget gate permits'
Write-Host "Smoke mode: $env:MINIVERSE_SMOKE_MODE"

while ($true) {
    try {
        Invoke-FreeMaintenance

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
            if ((Paid-Budget-Available) -and (Planner-Is-Due)) {
                $planner = "AHOS_BACKLOG_ITEM: PLANNER`nInspect ahos_core and AHOS_BACKLOG.json. If there are no safe pending development tasks, append at most three concrete low-risk Authority-B tasks that improve local reliability, tests, architecture, observability, or developer ergonomics. Keep IDs unique. Stay strictly inside the isolated ahos_core worktree and preserve the existing governance boundary. Use neutral local-development wording in task titles and descriptions. Modify only ahos_core/AHOS_BACKLOG.json and validate that it remains valid JSON."
                $result = Invoke-AhosTask 'PLANNER' $planner
                (Get-Date).ToUniversalTime().ToString('o') | Set-Content $PlannerStamp -Encoding ascii

                if ($result.status -eq 'completed') {
                    Commit-And-Push 'autopilot: refresh safe AHOS backlog'
                } else {
                    & git -C $Workspace restore --worktree --staged . | Out-Null
                }

                Clear-ActiveTask
            } else {
                Write-Host "FREE-ONLY: no paid planner call. Remaining daily budget USD $(Get-RemainingBudget)."
            }

            Start-Sleep -Seconds $IdleSleepSeconds
            continue
        }

        $taskId = [string]$next.id
        $title = [string]$next.title

        if (-not (Paid-Budget-Available)) {
            Write-Host "FREE-ONLY: $taskId waiting. Remaining daily budget USD $(Get-RemainingBudget); reserve USD $PaidTaskReserveUsd."
            Start-Sleep -Seconds $IdleSleepSeconds
            continue
        }

        $instructionLines = @(
            "AHOS_BACKLOG_ITEM: $taskId",
            "You are developing AHOS, the Autonomous Holding Operating System, in its isolated Git worktree.",
            "",
            "Implement backlog item ${taskId}: $title",
            "",
            [string]$next.task,
            "",
            "Hard boundaries:",
            "- Work only inside ahos_core.",
            "- Stay within existing Authority A/B and the isolated worktree.",
            "- Preserve governance and owner-approval requirements exactly.",
            "- Do not modify AHOS_BACKLOG.json; the controller owns backlog status.",
            "- Inspect existing code first, make the smallest coherent reversible change, and run relevant tests."
        )
        $instruction = $instructionLines -join [Environment]::NewLine

        Write-Host "Starting $taskId - $title"
        $result = Invoke-AhosTask $taskId $instruction

        if ($result.status -ne 'completed') {
            & git -C $Workspace restore --worktree --staged . | Out-Null
            Mark-Task $taskId 'blocked' ([string]$result.last_error)
            Commit-And-Push "autopilot: mark $taskId blocked"
            Clear-ActiveTask
            Start-Sleep -Seconds 30
            continue
        }

        if (-not (Test-AhosCore)) {
            & git -C $Workspace restore --worktree --staged . | Out-Null
            Mark-Task $taskId 'blocked' 'AHOS test suite failed after autonomous change.'
            Commit-And-Push "autopilot: mark $taskId blocked after test failure"
            Clear-ActiveTask
            Start-Sleep -Seconds 30
            continue
        }

        Mark-Task $taskId 'completed'
        Commit-And-Push "autopilot: complete $taskId $title"
        Clear-ActiveTask
        Write-Host "COMPLETED: $taskId"
        Start-Sleep -Seconds 30
    } catch {
        Write-Host "AUTOPILOT ERROR: $($_.Exception.Message)"
        Start-Sleep -Seconds $IdleSleepSeconds
    }
}
'@
Set-Content -Path $loopPath -Value $loop -Encoding utf8

# 4) Date-aware status display.
$statusPath = Join-Path $Root 'Status-Holding-Autopilot.ps1'
$statusScript = @'
param(
    [decimal]$DailyBudgetUsd = 0.10,
    [decimal]$PaidTaskReserveUsd = 0.035
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$PidFile = Join-Path $StateDir 'holding-autopilot.pid'
$OutLog = Join-Path $StateDir 'holding-autopilot.out.log'
$ErrLog = Join-Path $StateDir 'holding-autopilot.err.log'
$BudgetFile = Join-Path $StateDir 'holding-autopilot-budget.json'
$ActiveTaskFile = Join-Path $StateDir 'holding-autopilot-active-task.json'

if (Test-Path $PidFile) {
    $pidValue = [int](Get-Content $PidFile -Raw)
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "AHOS AUTOPILOT: RUNNING (PID $pidValue)"
    } else {
        Write-Host 'AHOS AUTOPILOT: STOPPED (stale PID file)'
    }
} else {
    Write-Host 'AHOS AUTOPILOT: STOPPED'
}

$today = (Get-Date).ToString('yyyy-MM-dd')
$spent = [decimal]0
if (Test-Path $BudgetFile) {
    try {
        $budget = Get-Content $BudgetFile -Raw | ConvertFrom-Json
        if ($budget.date -eq $today) {
            $spent = [decimal]$budget.spent_usd
        }
    } catch {}
}

$remaining = $DailyBudgetUsd - $spent
Write-Host "AI spend today ($today): USD $spent / USD $DailyBudgetUsd"
Write-Host "Paid-task reserve: USD $PaidTaskReserveUsd"

if ($remaining -ge $PaidTaskReserveUsd) {
    Write-Host "MODE: PAID-ELIGIBLE (remaining USD $remaining)"
} else {
    Write-Host "MODE: FREE-ONLY (paid AI paused; remaining USD $remaining)"
}

if (Test-Path $ActiveTaskFile) {
    try {
        $active = Get-Content $ActiveTaskFile -Raw | ConvertFrom-Json
        Write-Host "ACTIVE BACKLOG ITEM: $($active.backlog_id)"
        Write-Host "ACTIVE QUEUE TASK: $($active.queue_task_id)"
    } catch {}
}

Write-Host "`n--- RECENT LOG ---"
if (Test-Path $OutLog) {
    Get-Content $OutLog -Tail 50
}

if (Test-Path $ErrLog) {
    $err = Get-Content $ErrLog -Tail 20
    if ($err) {
        Write-Host "`n--- RECENT ERRORS ---"
        $err
    }
}
'@
Set-Content -Path $statusPath -Value $statusScript -Encoding utf8

# 5) Persist the hard cap locally without printing secrets.
$envPath = Join-Path $Root '.env.runtime'
if (Test-Path $envPath) {
    $envText = Get-Content $envPath -Raw
    if ($envText -match '(?m)^MINIVERSE_MAX_BUDGET_PER_RUN_USD=') {
        $envText = [regex]::Replace(
            $envText,
            '(?m)^MINIVERSE_MAX_BUDGET_PER_RUN_USD=.*$',
            "MINIVERSE_MAX_BUDGET_PER_RUN_USD=$TaskHardCapUsd"
        )
    } else {
        if (-not $envText.EndsWith("`n")) {
            $envText += "`r`n"
        }
        $envText += "MINIVERSE_MAX_BUDGET_PER_RUN_USD=$TaskHardCapUsd`r`n"
    }
    Set-Content -Path $envPath -Value $envText -Encoding utf8
}

# 6) Validate locally. These steps do not call OpenAI.
Write-Host "`n=== LOCAL VALIDATION (NO OPENAI API CALLS) ==="

[void][scriptblock]::Create((Get-Content $loopPath -Raw))
[void][scriptblock]::Create((Get-Content $statusPath -Raw))
Write-Host "PowerShell syntax: PASS"

& ".\.venv\Scripts\python.exe" -m pytest tests\test_execution.py tests\test_openhands_builder.py -q
if ($LASTEXITCODE -ne 0) {
    throw "Python tests failed."
}

# Stop the old worker before reinstalling the package so its executable is not locked.
if (Test-Path ".\Stop-Miniverse.ps1") {
    try {
        & ".\Stop-Miniverse.ps1"
    } catch {
        Write-Host "Worker stop warning: $($_.Exception.Message)"
    }
}

& ".\.venv\Scripts\python.exe" -m pip install --no-cache-dir .
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed."
}

Write-Host "`n=== GIT CHANGES ==="
git status --short

git add miniverse\config.py miniverse\openhands_builder.py Holding-Autopilot-Loop.ps1 Status-Holding-Autopilot.ps1
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git -c user.name="Harun Aslan" -c user.email="harun@local.invalid" commit -m "fix(ahos): enforce hard AI budgets and restart-safe tasks"
    if ($LASTEXITCODE -ne 0) {
        throw "git commit failed."
    }

    git push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "git push failed."
    }

    Write-Host "Git commit/push: PASS"
} else {
    Write-Host "No tracked code changes to commit."
}

Write-Host "`n=== DONE ==="
Write-Host "Autopilot remains STOPPED."
Write-Host "Per-task OpenHands hard cap: USD $TaskHardCapUsd"
Write-Host "Daily budget: USD $DailyBudgetUsd"
Write-Host "Restart duplicate protection: ENABLED"
Write-Host "Date-aware budget status/reset: ENABLED"
Write-Host "Free-first maintenance: ENABLED"
Write-Host ""
Write-Host "Next command when ready:"
Write-Host "  .\Start-Holding-Autopilot.ps1"
