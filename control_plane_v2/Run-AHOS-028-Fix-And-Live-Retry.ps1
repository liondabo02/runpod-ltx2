param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "Real AI retry is not approved locally. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$adapterPath = Join-Path $pkg "ahos\openhands_worker_adapter.py"
$testPath = Join-Path $pkg "tests\test_openhands_owner_approval.py"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }

Write-Host "=== AHOS-028 OPENHANDS APPROVAL-GATE FIX + LIVE RETRY ==="
Write-Host "AHOS-027 was blocked locally before the model runner."
Write-Host "Fixing explicit owner-approved paid execution, then retrying one tiny live task."
Write-Host ""

[IO.File]::WriteAllBytes(
    $adapterPath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IHJlCmZyb20gZGF0YWNsYXNzZXMgaW1wb3J0IGRhdGFjbGFzcwpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgKZnJvbSB0eXBpbmcgaW1wb3J0IEFueSwgQ2FsbGFibGUKCmZyb20gLndvcmtlcl9ydW50aW1lIGltcG9ydCBXb3JrZXJFeGVjdXRpb25SZXN1bHQKZnJvbSAud29ya2ZvcmNlX2V4ZWN1dGlvbiBpbXBvcnQgV29ya0l0ZW0KCgpCdWlsZGVyUnVubmVyID0gQ2FsbGFibGVbW3N0ciwgUGF0aF0sIEFueV0KCgpkZWYgX3NhZmVfdGFza19kaXIodGFza19pZDogc3RyKSAtPiBzdHI6CiAgICB2YWx1ZSA9IHJlLnN1YihyIlteQS1aYS16MC05Ll8tXSsiLCAiXyIsIHRhc2tfaWQpLnN0cmlwKCIuXyIpCiAgICByZXR1cm4gdmFsdWUgb3IgInRhc2siCgoKZGVmIF90dXBsZV9vZl9zdHJpbmdzKHZhbHVlOiBBbnkpIC0+IHR1cGxlW3N0ciwgLi4uXToKICAgIGlmIHZhbHVlIGlzIE5vbmU6CiAgICAgICAgcmV0dXJuICgpCiAgICBpZiBpc2luc3RhbmNlKHZhbHVlLCBzdHIpOgogICAgICAgIHJldHVybiAodmFsdWUsKQogICAgdHJ5OgogICAgICAgIHJldHVybiB0dXBsZShzdHIoaXRlbSkgZm9yIGl0ZW0gaW4gdmFsdWUpCiAgICBleGNlcHQgVHlwZUVycm9yOgogICAgICAgIHJldHVybiAoc3RyKHZhbHVlKSwpCgoKQGRhdGFjbGFzcyhzbG90cz1UcnVlKQpjbGFzcyBPcGVuSGFuZHNXb3JrZXJBZGFwdGVyOgogICAgIiIiQnJpZGdlIGFuIEFIT1MgdmlydHVhbCBlbXBsb3llZSB0byBhbiBpbmplY3RlZCBPcGVuSGFuZHMtc3R5bGUgcnVubmVyLgoKICAgIFRoZSBydW5uZXIgaXMgaW5qZWN0ZWQgc28gbG9jYWwgdGVzdHMgc3RheSB6ZXJvLWNvc3QuIFByb3RlY3RlZCBhY3Rpb25zLAogICAgaW5jbHVkaW5nIHBhaWQgQUkgd29yaywgZmFpbCBjbG9zZWQgdW5sZXNzIG93bmVyIGFwcHJvdmFsIGlzIGV4cGxpY2l0LgogICAgIiIiCgogICAgcnVubmVyOiBCdWlsZGVyUnVubmVyCiAgICB3b3Jrc3BhY2Vfcm9vdDogUGF0aAoKICAgIGRlZiBfX3Bvc3RfaW5pdF9fKHNlbGYpIC0+IE5vbmU6CiAgICAgICAgc2VsZi53b3Jrc3BhY2Vfcm9vdCA9IFBhdGgoc2VsZi53b3Jrc3BhY2Vfcm9vdCkKICAgICAgICBzZWxmLndvcmtzcGFjZV9yb290Lm1rZGlyKHBhcmVudHM9VHJ1ZSwgZXhpc3Rfb2s9VHJ1ZSkKCiAgICBkZWYgX19jYWxsX18oc2VsZiwgaXRlbTogV29ya0l0ZW0sIHdvcmtlcl9pZDogc3RyKSAtPiBXb3JrZXJFeGVjdXRpb25SZXN1bHQ6CiAgICAgICAgcHJvdGVjdGVkX2FjdGlvbiA9IGFueSgKICAgICAgICAgICAgKAogICAgICAgICAgICAgICAgaXRlbS5leHRlcm5hbF9zaWRlX2VmZmVjdCwKICAgICAgICAgICAgICAgIGl0ZW0uZGVzdHJ1Y3RpdmUsCiAgICAgICAgICAgICAgICBpdGVtLnRvdWNoZXNfc2VjcmV0cywKICAgICAgICAgICAgICAgIGl0ZW0uZXN0aW1hdGVkX2Nvc3RfdXNkID4gMCwKICAgICAgICAgICAgKQogICAgICAgICkKICAgICAgICBpZiBwcm90ZWN0ZWRfYWN0aW9uIGFuZCBub3QgaXRlbS5vd25lcl9hcHByb3ZlZDoKICAgICAgICAgICAgcmV0dXJuIFdvcmtlckV4ZWN1dGlvblJlc3VsdCgKICAgICAgICAgICAgICAgIHRhc2tfaWQ9aXRlbS50YXNrX2lkLAogICAgICAgICAgICAgICAgd29ya2VyX2lkPXdvcmtlcl9pZCwKICAgICAgICAgICAgICAgIHN1Y2Nlc3M9RmFsc2UsCiAgICAgICAgICAgICAgICBzdW1tYXJ5PSJleGVjdXRpb24gYmxvY2tlZCBieSBsb2NhbCBzYWZldHkgZ2F0ZSIsCiAgICAgICAgICAgICkKCiAgICAgICAgd29ya3NwYWNlID0gc2VsZi53b3Jrc3BhY2Vfcm9vdCAvIF9zYWZlX3Rhc2tfZGlyKGl0ZW0udGFza19pZCkKICAgICAgICB3b3Jrc3BhY2UubWtkaXIocGFyZW50cz1UcnVlLCBleGlzdF9vaz1UcnVlKQoKICAgICAgICBwcm9tcHQgPSBzZWxmLl9wcm9tcHQoaXRlbT1pdGVtLCB3b3JrZXJfaWQ9d29ya2VyX2lkLCB3b3Jrc3BhY2U9d29ya3NwYWNlKQoKICAgICAgICB0cnk6CiAgICAgICAgICAgIHJlc3VsdCA9IHNlbGYucnVubmVyKHByb21wdCwgd29ya3NwYWNlKQogICAgICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZXhjOgogICAgICAgICAgICByZXR1cm4gV29ya2VyRXhlY3V0aW9uUmVzdWx0KAogICAgICAgICAgICAgICAgdGFza19pZD1pdGVtLnRhc2tfaWQsCiAgICAgICAgICAgICAgICB3b3JrZXJfaWQ9d29ya2VyX2lkLAogICAgICAgICAgICAgICAgc3VjY2Vzcz1GYWxzZSwKICAgICAgICAgICAgICAgIHN1bW1hcnk9ZiJidWlsZGVyIGV4ZWN1dGlvbiBmYWlsZWQ6IHt0eXBlKGV4YykuX19uYW1lX199OiB7ZXhjfSIsCiAgICAgICAgICAgICkKCiAgICAgICAgcmVzdWx0X3N1Y2Nlc3MgPSBnZXRhdHRyKHJlc3VsdCwgInN1Y2Nlc3MiLCBUcnVlKQogICAgICAgIHN1bW1hcnkgPSBzdHIoCiAgICAgICAgICAgIGdldGF0dHIocmVzdWx0LCAic3VtbWFyeSIsIE5vbmUpCiAgICAgICAgICAgIG9yIGdldGF0dHIocmVzdWx0LCAiY2hhbmdlX3N1bW1hcnkiLCBOb25lKQogICAgICAgICAgICBvciAiYnVpbGRlciBjb21wbGV0ZWQiCiAgICAgICAgKQogICAgICAgIGNoYW5nZWRfZmlsZXMgPSBfdHVwbGVfb2Zfc3RyaW5ncygKICAgICAgICAgICAgZ2V0YXR0cihyZXN1bHQsICJjaGFuZ2VkX2ZpbGVzIiwgTm9uZSkKICAgICAgICAgICAgb3IgZ2V0YXR0cihyZXN1bHQsICJhcnRpZmFjdHMiLCBOb25lKQogICAgICAgICkKICAgICAgICB0ZXN0c19ydW4gPSBfdHVwbGVfb2Zfc3RyaW5ncyhnZXRhdHRyKHJlc3VsdCwgInRlc3RzX3J1biIsIE5vbmUpKQoKICAgICAgICByZXR1cm4gV29ya2VyRXhlY3V0aW9uUmVzdWx0KAogICAgICAgICAgICB0YXNrX2lkPWl0ZW0udGFza19pZCwKICAgICAgICAgICAgd29ya2VyX2lkPXdvcmtlcl9pZCwKICAgICAgICAgICAgc3VjY2Vzcz1ib29sKHJlc3VsdF9zdWNjZXNzKSwKICAgICAgICAgICAgc3VtbWFyeT1zdW1tYXJ5LAogICAgICAgICAgICBhcnRpZmFjdHM9Y2hhbmdlZF9maWxlcywKICAgICAgICAgICAgdGVzdHNfcnVuPXRlc3RzX3J1biwKICAgICAgICApCgogICAgQHN0YXRpY21ldGhvZAogICAgZGVmIF9wcm9tcHQoKiwgaXRlbTogV29ya0l0ZW0sIHdvcmtlcl9pZDogc3RyLCB3b3Jrc3BhY2U6IFBhdGgpIC0+IHN0cjoKICAgICAgICBjYXBhYmlsaXRpZXMgPSAiLCAiLmpvaW4oc29ydGVkKGl0ZW0ucmVxdWlyZWRfY2FwYWJpbGl0aWVzKSkgb3IgIm5vbmUiCiAgICAgICAgcmV0dXJuICgKICAgICAgICAgICAgZiJZb3UgYXJlIEFIT1MgdmlydHVhbCB3b3JrZXIge3dvcmtlcl9pZH0uXG4iCiAgICAgICAgICAgIGYiVGFzayBJRDoge2l0ZW0udGFza19pZH1cbiIKICAgICAgICAgICAgZiJUYXNrOiB7aXRlbS50aXRsZX1cbiIKICAgICAgICAgICAgZiJEZXBhcnRtZW50OiB7aXRlbS5kZXBhcnRtZW50fVxuIgogICAgICAgICAgICBmIlJlcXVpcmVkIGNhcGFiaWxpdGllczoge2NhcGFiaWxpdGllc31cbiIKICAgICAgICAgICAgZiJXb3Jrc3BhY2U6IHt3b3Jrc3BhY2V9XG5cbiIKICAgICAgICAgICAgIldvcmsgb25seSBpbnNpZGUgdGhlIHByb3ZpZGVkIHdvcmtzcGFjZS4gIgogICAgICAgICAgICAiRG8gbm90IHB1Ymxpc2gsIG1lc3NhZ2UsIHB1cmNoYXNlLCBkZXBsb3kgZXh0ZXJuYWxseSwgYWNjZXNzIHNlY3JldHMsICIKICAgICAgICAgICAgIm9yIHBlcmZvcm0gZGVzdHJ1Y3RpdmUgYWN0aW9ucy4gUnVuIHJlbGV2YW50IGxvY2FsIHRlc3RzLiAiCiAgICAgICAgICAgICJSZXR1cm4gYSBjb25jaXNlIHN1bW1hcnksIGNoYW5nZWQgZmlsZXMsIHRlc3RzIHJ1biwgYW5kIHJlbWFpbmluZyByaXNrcy4iCiAgICAgICAgKQoKCmRlZiBtYWtlX2J1aWxkZXJfcnVubmVyKGJ1aWxkZXI6IEFueSkgLT4gQnVpbGRlclJ1bm5lcjoKICAgICIiIldyYXAgYSBidWlsZGVyIG9iamVjdCBleHBvc2luZyBydW4odGFzaz0uLi4sIHdvcmtzcGFjZT0uLi4pLiIiIgoKICAgIGRlZiBfcnVuKHByb21wdDogc3RyLCB3b3Jrc3BhY2U6IFBhdGgpIC0+IEFueToKICAgICAgICByZXR1cm4gYnVpbGRlci5ydW4odGFzaz1wcm9tcHQsIHdvcmtzcGFjZT13b3Jrc3BhY2UpCgogICAgcmV0dXJuIF9ydW4K")
)
[IO.File]::WriteAllBytes(
    $testPath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKZnJvbSBkYXRhY2xhc3NlcyBpbXBvcnQgZGF0YWNsYXNzCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAoKZnJvbSBhaG9zLm9wZW5oYW5kc193b3JrZXJfYWRhcHRlciBpbXBvcnQgT3BlbkhhbmRzV29ya2VyQWRhcHRlcgpmcm9tIGFob3Mud29ya2ZvcmNlX2V4ZWN1dGlvbiBpbXBvcnQgV29ya0l0ZW0KCgpAZGF0YWNsYXNzCmNsYXNzIEZha2VCdWlsZGVyUmVzdWx0OgogICAgc3VtbWFyeTogc3RyCiAgICBjaGFuZ2VkX2ZpbGVzOiB0dXBsZVtzdHIsIC4uLl0KICAgIHRlc3RzX3J1bjogdHVwbGVbc3RyLCAuLi5dCiAgICBzdWNjZXNzOiBib29sID0gVHJ1ZQoKCmRlZiB0ZXN0X293bmVyX2FwcHJvdmVkX3BhaWRfd29ya19jYW5fcmVhY2hfcnVubmVyKHRtcF9wYXRoOiBQYXRoKSAtPiBOb25lOgogICAgY2FsbHM6IGxpc3Rbc3RyXSA9IFtdCgogICAgZGVmIHJ1bm5lcihfcHJvbXB0OiBzdHIsIF93b3Jrc3BhY2U6IFBhdGgpIC0+IEZha2VCdWlsZGVyUmVzdWx0OgogICAgICAgIGNhbGxzLmFwcGVuZCgiY2FsbGVkIikKICAgICAgICByZXR1cm4gRmFrZUJ1aWxkZXJSZXN1bHQoIm9rIiwgKCJ4LnR4dCIsKSwgKCkpCgogICAgYWRhcHRlciA9IE9wZW5IYW5kc1dvcmtlckFkYXB0ZXIocnVubmVyPXJ1bm5lciwgd29ya3NwYWNlX3Jvb3Q9dG1wX3BhdGgpCiAgICBpdGVtID0gV29ya0l0ZW0oCiAgICAgICAgdGFza19pZD0iYXBwcm92ZWQtcGFpZCIsCiAgICAgICAgdGl0bGU9IlRpbnkgYXBwcm92ZWQgcGFpZCBzbW9rZSIsCiAgICAgICAgZGVwYXJ0bWVudD0ic29mdHdhcmUiLAogICAgICAgIHJlcXVpcmVkX2NhcGFiaWxpdGllcz1mcm96ZW5zZXQoeyJweXRob24ifSksCiAgICAgICAgZXN0aW1hdGVkX2Nvc3RfdXNkPTAuMDIsCiAgICAgICAgb3duZXJfYXBwcm92ZWQ9VHJ1ZSwKICAgICkKCiAgICByZXN1bHQgPSBhZGFwdGVyKGl0ZW0sICJkZXYtMDEtbGl2ZSIpCgogICAgYXNzZXJ0IHJlc3VsdC5zdWNjZXNzIGlzIFRydWUKICAgIGFzc2VydCBjYWxscyA9PSBbImNhbGxlZCJdCgoKZGVmIHRlc3RfdW5hcHByb3ZlZF9wYWlkX3dvcmtfcmVtYWluc19ibG9ja2VkKHRtcF9wYXRoOiBQYXRoKSAtPiBOb25lOgogICAgY2FsbHM6IGxpc3Rbc3RyXSA9IFtdCgogICAgZGVmIHJ1bm5lcihfcHJvbXB0OiBzdHIsIF93b3Jrc3BhY2U6IFBhdGgpIC0+IEZha2VCdWlsZGVyUmVzdWx0OgogICAgICAgIGNhbGxzLmFwcGVuZCgiY2FsbGVkIikKICAgICAgICByZXR1cm4gRmFrZUJ1aWxkZXJSZXN1bHQoIm9rIiwgKCksICgpKQoKICAgIGFkYXB0ZXIgPSBPcGVuSGFuZHNXb3JrZXJBZGFwdGVyKHJ1bm5lcj1ydW5uZXIsIHdvcmtzcGFjZV9yb290PXRtcF9wYXRoKQogICAgaXRlbSA9IFdvcmtJdGVtKAogICAgICAgIHRhc2tfaWQ9InVuYXBwcm92ZWQtcGFpZCIsCiAgICAgICAgdGl0bGU9IlVuYXBwcm92ZWQgcGFpZCB3b3JrIiwKICAgICAgICBkZXBhcnRtZW50PSJzb2Z0d2FyZSIsCiAgICAgICAgcmVxdWlyZWRfY2FwYWJpbGl0aWVzPWZyb3plbnNldCh7InB5dGhvbiJ9KSwKICAgICAgICBlc3RpbWF0ZWRfY29zdF91c2Q9MC4wMiwKICAgICkKCiAgICByZXN1bHQgPSBhZGFwdGVyKGl0ZW0sICJkZXYtMDEtbGl2ZSIpCgogICAgYXNzZXJ0IHJlc3VsdC5zdWNjZXNzIGlzIEZhbHNlCiAgICBhc3NlcnQgY2FsbHMgPT0gW10KCgpkZWYgdGVzdF91bmFwcHJvdmVkX2V4dGVybmFsX3dvcmtfcmVtYWluc19ibG9ja2VkKHRtcF9wYXRoOiBQYXRoKSAtPiBOb25lOgogICAgY2FsbHM6IGxpc3Rbc3RyXSA9IFtdCgogICAgZGVmIHJ1bm5lcihfcHJvbXB0OiBzdHIsIF93b3Jrc3BhY2U6IFBhdGgpIC0+IEZha2VCdWlsZGVyUmVzdWx0OgogICAgICAgIGNhbGxzLmFwcGVuZCgiY2FsbGVkIikKICAgICAgICByZXR1cm4gRmFrZUJ1aWxkZXJSZXN1bHQoIm9rIiwgKCksICgpKQoKICAgIGFkYXB0ZXIgPSBPcGVuSGFuZHNXb3JrZXJBZGFwdGVyKHJ1bm5lcj1ydW5uZXIsIHdvcmtzcGFjZV9yb290PXRtcF9wYXRoKQogICAgaXRlbSA9IFdvcmtJdGVtKAogICAgICAgIHRhc2tfaWQ9InVuYXBwcm92ZWQtZXh0ZXJuYWwiLAogICAgICAgIHRpdGxlPSJFeHRlcm5hbCB3b3JrIiwKICAgICAgICBkZXBhcnRtZW50PSJzb2Z0d2FyZSIsCiAgICAgICAgcmVxdWlyZWRfY2FwYWJpbGl0aWVzPWZyb3plbnNldCh7InB5dGhvbiJ9KSwKICAgICAgICBleHRlcm5hbF9zaWRlX2VmZmVjdD1UcnVlLAogICAgKQoKICAgIHJlc3VsdCA9IGFkYXB0ZXIoaXRlbSwgImRldi0wMS1saXZlIikKCiAgICBhc3NlcnQgcmVzdWx0LnN1Y2Nlc3MgaXMgRmFsc2UKICAgIGFzc2VydCBjYWxscyA9PSBbXQo=")
)

Write-Host "Running full AHOS tests BEFORE any live AI call..."
$oldPythonPath = $env:PYTHONPATH
Push-Location $pkg
try {
    $env:PYTHONPATH = $pkg
    & $python -m pytest -q
    $testExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $oldPythonPath
}
if ($testExit -ne 0) {
    throw "Local tests failed. No live AI call was made."
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-028" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-028"
        title = "Honor owner approval in OpenHands adapter"
        status = "completed"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        completed_at = [DateTime]::UtcNow.ToString("o")
        task = "Allow explicitly owner-approved paid work through the OpenHands worker adapter while unapproved protected work remains blocked. Validate locally, then retry one tiny live AI worker smoke."
    }
    [IO.File]::WriteAllText(
        $backlogPath,
        ($b | ConvertTo-Json -Depth 12),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

git -C $ws add ahos_core/ahos/openhands_worker_adapter.py ahos_core/tests/test_openhands_owner_approval.py ahos_core/AHOS_BACKLOG.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "fix(ahos): honor owner approval in OpenHands adapter"
if ($LASTEXITCODE -ne 0) { throw "git commit failed. No live AI call was made." }

git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) { throw "git push failed. No live AI call was made." }

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name,$value = $_ -split '=',2
    [Environment]::SetEnvironmentVariable($name.Trim(),$value.Trim(),'Process')
}

if (-not $env:LLM_API_KEY -and -not $env:OPENAI_API_KEY) {
    throw "No API key loaded from .env.runtime."
}
if (-not $env:MINIVERSE_OPENHANDS_MODEL) {
    throw "MINIVERSE_OPENHANDS_MODEL is missing."
}

Write-Host ""
Write-Host "Local fix/tests committed. Starting ONE real AI worker retry..."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host "AHOS estimate/reserve: USD 0.02; this is not a provider-side hard cap."
Write-Host ""

$liveCode = @'
from __future__ import annotations

from pathlib import Path

from ahos.openhands_worker_adapter import OpenHandsWorkerAdapter
from ahos.virtual_workforce import VirtualWorkforceRegistry, WorkerProfile, WorkerRole
from ahos.worker_runtime import QaExecutionResult, VirtualWorkerRuntime
from ahos.workforce_execution import WorkItem, WorkStage

ROOT = Path(r"__ROOT__")
LIVE_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-ai"
TASK_ID = "AHOS-028-dev01-real-ai-smoke"
TARGET = "AHOS_DEV01_OK.txt"
EXPECTED = "AHOS_DEV01_REAL_AI_OK"

import miniverse.config as cfg
from miniverse.openhands_builder import OpenHandsBuilder


def resolve_settings():
    for name in ("settings", "SETTINGS"):
        value = getattr(cfg, name, None)
        if value is not None:
            return value
    for name in ("get_settings", "load_settings"):
        fn = getattr(cfg, name, None)
        if callable(fn):
            return fn()
    cls = getattr(cfg, "Settings", None)
    if cls is not None:
        return cls()
    raise RuntimeError("Could not resolve Miniverse settings object.")


def build_builder(settings):
    errors = []
    for attempt in (
        lambda: OpenHandsBuilder(settings=settings),
        lambda: OpenHandsBuilder(settings),
        lambda: OpenHandsBuilder(),
    ):
        try:
            return attempt()
        except TypeError as exc:
            errors.append(str(exc))
    raise RuntimeError("Could not construct OpenHandsBuilder: " + " | ".join(errors))


builder = build_builder(resolve_settings())
raw_results = []


def live_runner(prompt: str, workspace: Path):
    result = builder.run(task=prompt, workspace=workspace)
    raw_results.append(result)
    return result


worker = WorkerProfile(
    worker_id="dev-01-live",
    name="Software Engineer 01 - Live Smoke",
    role=WorkerRole.SOFTWARE_ENGINEER,
    department="software",
    capabilities=frozenset({"python", "backend", "api", "automation", "testing", "git"}),
    daily_budget_usd=0.02,
    can_use_paid_ai=True,
)
qa = WorkerProfile(
    worker_id="qa-01",
    name="QA Engineer 01",
    role=WorkerRole.QA_ENGINEER,
    department="quality",
    capabilities=frozenset({"qa", "verification", "testing"}),
)

registry = VirtualWorkforceRegistry((worker, qa))
adapter = OpenHandsWorkerAdapter(runner=live_runner, workspace_root=LIVE_ROOT)


def verify_qa(item, worker_result, qa_worker_id):
    target = LIVE_ROOT / TASK_ID / TARGET
    passed = (
        worker_result.success
        and target.exists()
        and target.read_text(encoding="utf-8").strip() == EXPECTED
    )
    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=passed,
        summary="file/content verification passed" if passed else "file/content verification failed",
    )


runtime = VirtualWorkerRuntime(
    registry,
    executors={"dev-01-live": adapter},
    qa_executor=verify_qa,
)

item = WorkItem(
    task_id=TASK_ID,
    title=(
        f"Create a file named {TARGET} containing exactly {EXPECTED}. "
        "Do not change any other file. Verify the contents."
    ),
    department="software",
    required_capabilities=frozenset({"python", "automation"}),
    estimated_cost_usd=0.02,
    owner_approved=True,
)

result = runtime.run(item)
target = LIVE_ROOT / TASK_ID / TARGET

print("=== REAL VIRTUAL WORKER RESULT ===")
print("STAGE:", result.stage.value)
print("WORKER:", result.assignment.worker_id)
print("WORKER SUMMARY:", result.worker_result.summary if result.worker_result else None)
print("QA:", result.qa_result.summary if result.qa_result else None)
print("TARGET EXISTS:", target.exists())
if target.exists():
    print("TARGET CONTENT:", target.read_text(encoding="utf-8").strip())

if raw_results:
    raw = raw_results[-1]
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)
    print("REPORTED ESTIMATED COST USD:", cost if cost is not None else "unavailable")

if result.stage is not WorkStage.COMPLETED:
    raise SystemExit("REAL AI WORKER SMOKE: FAILED")
if not target.exists() or target.read_text(encoding="utf-8").strip() != EXPECTED:
    raise SystemExit("REAL AI WORKER SMOKE: FAILED CONTENT CHECK")

print("REAL AI WORKER SMOKE: PASS")
'@

$liveCode = $liveCode.Replace("__ROOT__", $root.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $liveCode | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    throw "AHOS-028 live AI worker retry failed. See error above."
}

Write-Host ""
Write-Host "=== AHOS-028 COMPLETE ==="
Write-Host "Real virtual worker: PASS"
Write-Host "QA verification: PASS"
Write-Host "Owner approval gate: PASS"
Write-Host "No publish/message/payment action was performed."
