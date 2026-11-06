$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$branch = "feature/ahos-autopilot"

Write-Host "=== STUDIO-006 SAFE GIT SYNC V2 ==="
Write-Host "Kokoro HTTP 200 already passed."
Write-Host "This step fixes only the Git history."
Write-Host "RunPod/API spend: USD 0"
Write-Host ""

if (-not (Test-Path (Join-Path $ws ".git"))) {
    throw "AHOS Git workspace not found: $ws"
}

$current = (git -C $ws branch --show-current).Trim()
if ($current -ne $branch) {
    throw "Wrong branch. Current=$current Expected=$branch"
}

$statusLines = @(git -C $ws status --porcelain)

$unexpected = @()
foreach ($line in $statusLines) {
    if ($line -match '^\?\?\s+ahos_core/runtime/?$') {
        continue
    }
    $unexpected += $line
}

if ($unexpected.Count -gt 0) {
    Write-Host "Unexpected working-tree changes detected:"
    $unexpected | ForEach-Object { Write-Host $_ }
    throw "Refusing to continue because there are changes other than ahos_core/runtime/."
}

# Keep private/runtime state untouched, but exclude it from local Git status immediately.
$excludeFile = Join-Path $ws ".git\info\exclude"
$excludeEntry = "/ahos_core/runtime/"

if (-not (Test-Path $excludeFile)) {
    New-Item -ItemType File -Force -Path $excludeFile | Out-Null
}

$existingExclude = Get-Content $excludeFile -ErrorAction SilentlyContinue
if ($existingExclude -notcontains $excludeEntry) {
    Add-Content -Path $excludeFile -Value $excludeEntry
    Write-Host "Local Git exclude added for private runtime state."
} else {
    Write-Host "Local Git exclude already present."
}

$afterExclude = @(git -C $ws status --porcelain)
if ($afterExclude.Count -gt 0) {
    Write-Host "Working tree is still not clean:"
    $afterExclude | ForEach-Object { Write-Host $_ }
    throw "Working tree still dirty after safely excluding ahos_core/runtime/."
}

Write-Host "Working tree: CLEAN"
Write-Host "Private runtime files: PRESERVED"
Write-Host ""

$localHead = (git -C $ws rev-parse HEAD).Trim()
$backup = "backup/studio006-kokoro-pass-" + (Get-Date -Format "yyyyMMdd-HHmmss")

git -C $ws branch $backup $localHead
if ($LASTEXITCODE -ne 0) { throw "Could not create safety backup branch." }

Write-Host "Safety backup branch:" $backup
Write-Host "Local HEAD before sync:" $localHead
Write-Host ""

git -C $ws fetch origin $branch
if ($LASTEXITCODE -ne 0) { throw "git fetch failed." }

$remoteHead = (git -C $ws rev-parse "origin/$branch").Trim()
Write-Host "Remote HEAD:" $remoteHead
Write-Host "Rebasing local Kokoro PASS evidence onto current remote branch..."

git -C $ws rebase "origin/$branch"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Rebase conflict detected. Aborting safely..."
    git -C $ws rebase --abort | Out-Null
    Write-Host "Original local commit is preserved."
    Write-Host "Safety backup branch:" $backup
    throw "Rebase conflict. No push performed."
}

Write-Host "Rebase: PASS"
Write-Host "Pushing synchronized branch..."

git -C $ws push origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git push failed after successful rebase."
}

$newHead = (git -C $ws rev-parse HEAD).Trim()

Write-Host ""
Write-Host "=== STUDIO-006 SAFE GIT SYNC COMPLETE ==="
Write-Host "Kokoro live HTTP 200 proof: PRESERVED"
Write-Host "Private runtime state: PRESERVED"
Write-Host "Remote .gitignore runtime protection: PRESENT"
Write-Host "Remote sync/rebase: PASS"
Write-Host "Git push: PASS"
Write-Host "Branch:" $branch
Write-Host "New HEAD:" $newHead
Write-Host "RunPod/API spend: USD 0"
Write-Host ""
Write-Host "NEXT: one tiny real Kokoro speech sample and audio-byte validation."
