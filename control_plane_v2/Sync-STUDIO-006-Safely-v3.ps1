$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$branch = "feature/ahos-autopilot"
$reportRel = "ahos_core/reports/STUDIO-006-kokoro-live-health.json"

Write-Host "=== STUDIO-006 SAFE GIT ALIGN V3 ==="
Write-Host "Kokoro HTTP 200 already passed."
Write-Host "Remote PASS report has already been written to GitHub."
Write-Host "This step only aligns the local branch safely."
Write-Host "RunPod/API spend: USD 0"
Write-Host ""

if (-not (Test-Path $ws)) {
    throw "AHOS workspace not found: $ws"
}

$current = (git -C $ws branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not read current Git branch." }

if ($current -ne $branch) {
    throw "Wrong branch. Current=$current Expected=$branch"
}

# Refuse to touch tracked local edits.
$trackedDirty = @(git -C $ws status --porcelain --untracked-files=no)
if ($trackedDirty.Count -gt 0) {
    Write-Host "Tracked local changes detected:"
    $trackedDirty | ForEach-Object { Write-Host $_ }
    throw "Refusing to align while tracked local changes exist."
}

Write-Host "Tracked working tree: CLEAN"
Write-Host "Local runtime/untracked files will be left untouched."
Write-Host ""

git -C $ws fetch origin $branch
if ($LASTEXITCODE -ne 0) { throw "git fetch failed." }

$remoteHead = (git -C $ws rev-parse "origin/$branch").Trim()
$localHead  = (git -C $ws rev-parse HEAD).Trim()

Write-Host "Local HEAD :" $localHead
Write-Host "Remote HEAD:" $remoteHead
Write-Host ""

# Verify that the authoritative Kokoro PASS report is on the remote branch.
$remoteReport = git -C $ws show "origin/$branch`:$reportRel"
if ($LASTEXITCODE -ne 0) {
    throw "Remote Kokoro PASS report is missing. Refusing to reset."
}

$remoteText = ($remoteReport -join "`n")
if ($remoteText -notmatch '"status"\s*:\s*"PASS"' -or
    $remoteText -notmatch '"http_status"\s*:\s*200') {
    throw "Remote Kokoro report does not contain PASS + HTTP 200. Refusing to reset."
}

Write-Host "Remote Kokoro PASS report: VERIFIED"

# Only allow the known redundant local Kokoro health commit(s).
$localOnly = @(git -C $ws log --format="%H`t%s" "origin/$branch..HEAD")
if ($localOnly.Count -gt 0) {
    Write-Host "Local-only commits:"
    $localOnly | ForEach-Object { Write-Host "  $_" }

    foreach ($entry in $localOnly) {
        $parts = $entry -split "`t", 2
        $subject = if ($parts.Count -gt 1) { $parts[1] } else { "" }

        if ($subject -notin @(
            "test(studio): verify fresh Kokoro worker health",
            "test(studio): verify Kokoro health after disk fix",
            "test(studio): verify Kokoro load balancer health"
        )) {
            throw "Unexpected local-only commit found: $subject"
        }
    }
}

# Safety branch preserves the exact pre-alignment local history.
$backup = "backup/studio006-pre-align-" + (Get-Date -Format "yyyyMMdd-HHmmss")
git -C $ws branch $backup $localHead
if ($LASTEXITCODE -ne 0) { throw "Could not create safety backup branch." }

Write-Host "Safety backup branch:" $backup
Write-Host ""
Write-Host "Aligning local branch to authoritative remote branch..."

git -C $ws reset --hard "origin/$branch"
if ($LASTEXITCODE -ne 0) { throw "git reset --hard failed." }

$newHead = (git -C $ws rev-parse HEAD).Trim()
$statusAfter = @(git -C $ws status --porcelain)

Write-Host ""
Write-Host "=== STUDIO-006 SAFE GIT ALIGN COMPLETE ==="
Write-Host "Kokoro live HTTP 200 proof: PRESERVED ON GITHUB"
Write-Host "Remote PASS report: VERIFIED"
Write-Host "Safety backup branch: $backup"
Write-Host "Local branch aligned: PASS"
Write-Host "New HEAD:" $newHead
Write-Host "RunPod/API spend: USD 0"

if ($statusAfter.Count -eq 0) {
    Write-Host "Working tree: CLEAN"
} else {
    Write-Host "Working tree has only local/untracked state:"
    $statusAfter | ForEach-Object { Write-Host "  $_" }
}

Write-Host ""
Write-Host "NEXT: generate one tiny real Kokoro speech sample and validate the audio bytes."
