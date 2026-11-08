$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$backlogPath = Join-Path $ws "ahos_core\AHOS_BACKLOG.json"

if (-not (Test-Path $backlogPath)) {
    throw "AHOS_BACKLOG.json not found: $backlogPath"
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json

$newTasks = @(
    [pscustomobject]@{
        id = "AHOS-011"
        title = "Add opportunity intake and local scoring model"
        status = "pending"
        risk = "low"
        authority = "B"
        requires_owner_approval = $false
        task = "Inside ahos_core only, implement a local opportunity intake model and deterministic scoring pipeline for potential work, products, services, and internal initiatives. Store source, category, expected value, effort, risk, confidence, strategic fit, and status. Keep it local and inert: no scraping, outreach, purchasing, publishing, or external side effects. Add focused tests."
    },
    [pscustomobject]@{
        id = "AHOS-012"
        title = "Add venture registry and lifecycle state machine"
        status = "pending"
        risk = "low"
        authority = "B"
        requires_owner_approval = $false
        task = "Inside ahos_core only, add a persistent local venture/company registry with lifecycle states such as idea, validating, building, operating, paused, and retired. Link ventures to opportunities, departments, objectives, budgets, and audit metadata. Enforce deterministic valid state transitions and add focused tests. No external side effects."
    },
    [pscustomobject]@{
        id = "AHOS-013"
        title = "Add work order and department assignment model"
        status = "pending"
        risk = "low"
        authority = "B"
        requires_owner_approval = $false
        task = "Inside ahos_core only, implement local work orders that turn approved venture objectives into bounded assignments for departments. Include work-order IDs, venture ID, mission ID, capability requirements, priority, dependencies, budget ceiling metadata, routing result, status, and audit correlation. Keep execution inert and add focused tests."
    },
    [pscustomobject]@{
        id = "AHOS-014"
        title = "Add local financial ledger and unit economics snapshot"
        status = "pending"
        risk = "low"
        authority = "B"
        requires_owner_approval = $false
        task = "Inside ahos_core only, implement a local append-only financial ledger for simulated or recorded revenue, costs, commitments, and budget allocations plus deterministic venture-level unit economics snapshots. Do not initiate payments, purchases, transfers, billing, or other external financial actions. Add focused tests."
    }
)

foreach ($t in $newTasks) {
    if (-not ($b.tasks | Where-Object { $_.id -eq $t.id })) {
        $b.tasks += $t
    }
}

$tmp = "$backlogPath.tmp"
$json = $b | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))
Get-Content $tmp -Raw | ConvertFrom-Json | Out-Null
Move-Item $tmp $backlogPath -Force

Write-Host "=== HOLDING OPERATING LAYER BACKLOG ==="
(Get-Content $backlogPath -Raw | ConvertFrom-Json).tasks |
    Where-Object { $_.id -in @("AHOS-011","AHOS-012","AHOS-013","AHOS-014") } |
    Select-Object id,title,status,risk,authority,requires_owner_approval |
    Format-Table -AutoSize

git -C $ws add ahos_core/AHOS_BACKLOG.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "plan(ahos): add holding operating layer backlog"
if ($LASTEXITCODE -ne 0) {
    $status = git -C $ws status --short
    if ($status) { throw "git commit failed." }
}

git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) { throw "git push failed." }

Write-Host ""
Write-Host "=== AHOS-011..014 PLANNED ==="
Write-Host "Backlog JSON: VALID"
Write-Host "Git push: PASS"
Write-Host "OpenAI API calls: 0"
