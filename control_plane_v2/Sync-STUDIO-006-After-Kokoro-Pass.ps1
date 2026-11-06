$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$branch = "feature/ahos-autopilot"

Write-Host "=== STUDIO-006 GIT SYNC AFTER KOKORO HEALTH PASS ==="
Write-Host "Kokoro HTTP 200 already passed."
Write-Host "This step only synchronizes Git history."
Write-Host "RunPod/API spend: USD 0"
Write-Host ""

if (-not (Test-Path (Join-Path $ws ".git"))) {
    throw "AHOS Git workspace not found: $ws"
}

$current = (git -C $ws branch --show-current).Trim()
if ($current -ne $branch) {
    throw "Wrong branch. Current=$current Expected=$branch"
}

$dirty = git -C $ws status --porcelain
if ($dirty) {
    Write-Host "Working tree has uncommitted changes:"
    Write-Host $dirty
    throw "Refusing to rebase a dirty working tree."
}

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
Write-Host "Rebasing local Kokoro health proof onto current remote branch..."

git -C $ws rebase "origin/$branch"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Rebase conflict detected. Aborting safely..."
    git -C $ws rebase --abort | Out-Null
    Write-Host "Your original local commit is preserved."
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
Write-Host "=== STUDIO-006 GIT SYNC COMPLETE ==="
Write-Host "Kokoro live /health HTTP 200: PASS"
Write-Host "Evidence commit preserved: PASS"
Write-Host "Remote sync/rebase: PASS"
Write-Host "Git push: PASS"
Write-Host "Branch:" $branch
Write-Host "New HEAD:" $newHead
Write-Host "RunPod/API spend: USD 0"
Write-Host ""
Write-Host "NEXT: generate one tiny real Kokoro speech sample and validate the audio bytes."
