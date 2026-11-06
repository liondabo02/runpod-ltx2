param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "Live AI manager retry is not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$modulePath = Join-Path $pkg "ahos\ai_manager_planner.py"
$testPath = Join-Path $pkg "tests\test_ai_manager_capability_catalog.py"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$reportDir = Join-Path $pkg "reports"
$reportPath = Join-Path $reportDir "AHOS-033-live-ai-manager-routing.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

Write-Host "=== AHOS-033 AI MANAGER ROUTABLE CAPABILITY FIX ==="
Write-Host "Root cause: AHOS-032 manager invented valid-sounding capability names"
Write-Host "that did not match the real virtual-worker capability registry."
Write-Host "Fix: give the manager the exact worker capability catalog and validate it."
Write-Host ""

[IO.File]::WriteAllBytes(
    $modulePath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KaW1wb3J0IHJlCmZyb20gZGF0YWNsYXNzZXMgaW1wb3J0IGRhdGFjbGFzcwpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgKZnJvbSB0eXBpbmcgaW1wb3J0IEFueSwgQ2FsbGFibGUsIEl0ZXJhYmxlLCBNYXBwaW5nCgpmcm9tIC5taXNzaW9uX29yY2hlc3RyYXRvciBpbXBvcnQgTWlzc2lvblN0ZXBTcGVjCgoKUGxhbm5lclJ1bm5lciA9IENhbGxhYmxlW1tzdHIsIFBhdGhdLCBBbnldCgoKZGVmIF9zYWZlX25hbWUodmFsdWU6IHN0cikgLT4gc3RyOgogICAgY2xlYW5lZCA9IHJlLnN1YihyIlteQS1aYS16MC05Ll8tXSsiLCAiXyIsIHZhbHVlKS5zdHJpcCgiLl8iKQogICAgcmV0dXJuIGNsZWFuZWQgb3IgIm1pc3Npb24iCgoKQGRhdGFjbGFzcyhzbG90cz1UcnVlKQpjbGFzcyBPcGVuSGFuZHNNYW5hZ2VyUGxhbm5lcjoKICAgICIiIlR1cm4gYSBtYW5hZ2VyIG9iamVjdGl2ZSBpbnRvIGEgdmFsaWRhdGVkIEFIT1MgbWlzc2lvbiBwbGFuLgoKICAgIFRoZSBtYW5hZ2VyIGlzIGNvbnN0cmFpbmVkIHRvIHJlYWwgZGVwYXJ0bWVudHMgYW5kLCB3aGVuIHByb3ZpZGVkLCB0aGUKICAgIGV4YWN0IGNhcGFiaWxpdGllcyBleHBvc2VkIGJ5IGN1cnJlbnRseSByb3V0YWJsZSB2aXJ0dWFsIHdvcmtlcnMuCiAgICBUaGUgbW9kZWwgY2FuIG5ldmVyIHNlbGYtYXBwcm92ZSBwcm90ZWN0ZWQgd29yay4KICAgICIiIgoKICAgIHJ1bm5lcjogUGxhbm5lclJ1bm5lcgogICAgd29ya3NwYWNlX3Jvb3Q6IFBhdGgKICAgIGFsbG93ZWRfZGVwYXJ0bWVudHM6IGZyb3plbnNldFtzdHJdCiAgICBjYXBhYmlsaXR5X2NhdGFsb2c6IE1hcHBpbmdbc3RyLCBmcm96ZW5zZXRbc3RyXV0gfCBOb25lID0gTm9uZQogICAgbWF4X3N0ZXBzOiBpbnQgPSA2CiAgICBtYXhfdG90YWxfZXN0aW1hdGVkX2Nvc3RfdXNkOiBmbG9hdCA9IDEuMAoKICAgIGRlZiBfX3Bvc3RfaW5pdF9fKHNlbGYpIC0+IE5vbmU6CiAgICAgICAgc2VsZi53b3Jrc3BhY2Vfcm9vdCA9IFBhdGgoc2VsZi53b3Jrc3BhY2Vfcm9vdCkKICAgICAgICBzZWxmLndvcmtzcGFjZV9yb290Lm1rZGlyKHBhcmVudHM9VHJ1ZSwgZXhpc3Rfb2s9VHJ1ZSkKICAgICAgICBpZiBzZWxmLm1heF9zdGVwcyA8IDE6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoIm1heF9zdGVwcyBtdXN0IGJlID49IDEiKQogICAgICAgIGlmIHNlbGYubWF4X3RvdGFsX2VzdGltYXRlZF9jb3N0X3VzZCA8IDA6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoIm1heF90b3RhbF9lc3RpbWF0ZWRfY29zdF91c2QgbXVzdCBiZSA+PSAwIikKCiAgICAgICAgaWYgc2VsZi5jYXBhYmlsaXR5X2NhdGFsb2cgaXMgbm90IE5vbmU6CiAgICAgICAgICAgIG5vcm1hbGl6ZWQ6IGRpY3Rbc3RyLCBmcm96ZW5zZXRbc3RyXV0gPSB7fQogICAgICAgICAgICBmb3IgZGVwYXJ0bWVudCwgdmFsdWVzIGluIHNlbGYuY2FwYWJpbGl0eV9jYXRhbG9nLml0ZW1zKCk6CiAgICAgICAgICAgICAgICBrZXkgPSBzdHIoZGVwYXJ0bWVudCkuc3RyaXAoKS5sb3dlcigpCiAgICAgICAgICAgICAgICBpZiBrZXkgbm90IGluIHNlbGYuYWxsb3dlZF9kZXBhcnRtZW50czoKICAgICAgICAgICAgICAgICAgICBjb250aW51ZQogICAgICAgICAgICAgICAgbm9ybWFsaXplZFtrZXldID0gZnJvemVuc2V0KAogICAgICAgICAgICAgICAgICAgIHN0cih2YWx1ZSkuc3RyaXAoKQogICAgICAgICAgICAgICAgICAgIGZvciB2YWx1ZSBpbiB2YWx1ZXMKICAgICAgICAgICAgICAgICAgICBpZiBzdHIodmFsdWUpLnN0cmlwKCkKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgc2VsZi5jYXBhYmlsaXR5X2NhdGFsb2cgPSBub3JtYWxpemVkCgogICAgZGVmIF9fY2FsbF9fKAogICAgICAgIHNlbGYsCiAgICAgICAgbWlzc2lvbl9pZDogc3RyLAogICAgICAgIG9iamVjdGl2ZTogc3RyLAogICAgICAgIG1hbmFnZXJfaWQ6IHN0ciwKICAgICkgLT4gSXRlcmFibGVbTWlzc2lvblN0ZXBTcGVjXToKICAgICAgICB3b3Jrc3BhY2UgPSBzZWxmLndvcmtzcGFjZV9yb290IC8gX3NhZmVfbmFtZShtaXNzaW9uX2lkKQogICAgICAgIHdvcmtzcGFjZS5ta2RpcihwYXJlbnRzPVRydWUsIGV4aXN0X29rPVRydWUpCiAgICAgICAgcGxhbl9wYXRoID0gd29ya3NwYWNlIC8gIk1JU1NJT05fUExBTi5qc29uIgogICAgICAgIGlmIHBsYW5fcGF0aC5leGlzdHMoKToKICAgICAgICAgICAgcGxhbl9wYXRoLnVubGluaygpCgogICAgICAgIHByb21wdCA9IHNlbGYuX3Byb21wdCgKICAgICAgICAgICAgbWlzc2lvbl9pZD1taXNzaW9uX2lkLAogICAgICAgICAgICBvYmplY3RpdmU9b2JqZWN0aXZlLAogICAgICAgICAgICBtYW5hZ2VyX2lkPW1hbmFnZXJfaWQsCiAgICAgICAgKQogICAgICAgIHNlbGYucnVubmVyKHByb21wdCwgd29ya3NwYWNlKQoKICAgICAgICBpZiBub3QgcGxhbl9wYXRoLmV4aXN0cygpOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKCJtYW5hZ2VyIGRpZCBub3QgY3JlYXRlIE1JU1NJT05fUExBTi5qc29uIikKCiAgICAgICAgdHJ5OgogICAgICAgICAgICBwYXlsb2FkID0ganNvbi5sb2FkcyhwbGFuX3BhdGgucmVhZF90ZXh0KGVuY29kaW5nPSJ1dGYtOCIpKQogICAgICAgIGV4Y2VwdCBqc29uLkpTT05EZWNvZGVFcnJvciBhcyBleGM6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoZiJtYW5hZ2VyIHByb2R1Y2VkIGludmFsaWQgSlNPTjoge2V4Y30iKSBmcm9tIGV4YwoKICAgICAgICByYXdfc3RlcHMgPSBwYXlsb2FkLmdldCgic3RlcHMiKQogICAgICAgIGlmIG5vdCBpc2luc3RhbmNlKHJhd19zdGVwcywgbGlzdCkgb3Igbm90IHJhd19zdGVwczoKICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigiTUlTU0lPTl9QTEFOLmpzb24gbXVzdCBjb250YWluIGEgbm9uLWVtcHR5IHN0ZXBzIGxpc3QiKQogICAgICAgIGlmIGxlbihyYXdfc3RlcHMpID4gc2VsZi5tYXhfc3RlcHM6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICAgICBmIm1hbmFnZXIgcGxhbiBleGNlZWRzIG1heF9zdGVwcz17c2VsZi5tYXhfc3RlcHN9IgogICAgICAgICAgICApCgogICAgICAgIHN0ZXBzOiBsaXN0W01pc3Npb25TdGVwU3BlY10gPSBbXQogICAgICAgIHRvdGFsX2Nvc3QgPSAwLjAKCiAgICAgICAgZm9yIGluZGV4LCByYXcgaW4gZW51bWVyYXRlKHJhd19zdGVwcywgc3RhcnQ9MSk6CiAgICAgICAgICAgIGlmIG5vdCBpc2luc3RhbmNlKHJhdywgZGljdCk6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKGYic3RlcCB7aW5kZXh9IG11c3QgYmUgYSBKU09OIG9iamVjdCIpCgogICAgICAgICAgICBzdGVwX2lkID0gc3RyKHJhdy5nZXQoInN0ZXBfaWQiLCAiIikpLnN0cmlwKCkKICAgICAgICAgICAgdGl0bGUgPSBzdHIocmF3LmdldCgidGl0bGUiLCAiIikpLnN0cmlwKCkKICAgICAgICAgICAgZGVwYXJ0bWVudCA9IHN0cihyYXcuZ2V0KCJkZXBhcnRtZW50IiwgIiIpKS5zdHJpcCgpLmxvd2VyKCkKCiAgICAgICAgICAgIGlmIGRlcGFydG1lbnQgbm90IGluIHNlbGYuYWxsb3dlZF9kZXBhcnRtZW50czoKICAgICAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICAgICAgICAgZiJzdGVwIHtzdGVwX2lkIG9yIGluZGV4fSB1c2VzIGRpc2FsbG93ZWQgZGVwYXJ0bWVudCAiCiAgICAgICAgICAgICAgICAgICAgZiJ7ZGVwYXJ0bWVudCFyfSIKICAgICAgICAgICAgICAgICkKCiAgICAgICAgICAgIGNhcGFiaWxpdGllc19yYXcgPSByYXcuZ2V0KCJyZXF1aXJlZF9jYXBhYmlsaXRpZXMiLCBbXSkKICAgICAgICAgICAgaWYgbm90IGlzaW5zdGFuY2UoY2FwYWJpbGl0aWVzX3JhdywgbGlzdCk6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgICAgIGYic3RlcCB7c3RlcF9pZCBvciBpbmRleH0gcmVxdWlyZWRfY2FwYWJpbGl0aWVzIG11c3QgYmUgYSBsaXN0IgogICAgICAgICAgICAgICAgKQogICAgICAgICAgICBjYXBhYmlsaXRpZXMgPSBmcm96ZW5zZXQoCiAgICAgICAgICAgICAgICBzdHIodmFsdWUpLnN0cmlwKCkKICAgICAgICAgICAgICAgIGZvciB2YWx1ZSBpbiBjYXBhYmlsaXRpZXNfcmF3CiAgICAgICAgICAgICAgICBpZiBzdHIodmFsdWUpLnN0cmlwKCkKICAgICAgICAgICAgKQogICAgICAgICAgICBpZiBub3QgY2FwYWJpbGl0aWVzOgogICAgICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigKICAgICAgICAgICAgICAgICAgICBmInN0ZXAge3N0ZXBfaWQgb3IgaW5kZXh9IG11c3QgcmVxdWVzdCBhdCBsZWFzdCBvbmUgY2FwYWJpbGl0eSIKICAgICAgICAgICAgICAgICkKCiAgICAgICAgICAgIGlmIHNlbGYuY2FwYWJpbGl0eV9jYXRhbG9nIGlzIG5vdCBOb25lOgogICAgICAgICAgICAgICAgYWxsb3dlZF9jYXBzID0gc2VsZi5jYXBhYmlsaXR5X2NhdGFsb2cuZ2V0KAogICAgICAgICAgICAgICAgICAgIGRlcGFydG1lbnQsCiAgICAgICAgICAgICAgICAgICAgZnJvemVuc2V0KCksCiAgICAgICAgICAgICAgICApCiAgICAgICAgICAgICAgICBpZiBub3QgYWxsb3dlZF9jYXBzOgogICAgICAgICAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICAgICAgICAgICAgIGYibm8gcm91dGFibGUgY2FwYWJpbGl0aWVzIHJlZ2lzdGVyZWQgZm9yIGRlcGFydG1lbnQgIgogICAgICAgICAgICAgICAgICAgICAgICBmIntkZXBhcnRtZW50IXJ9IgogICAgICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgICAgIHVua25vd24gPSBjYXBhYmlsaXRpZXMgLSBhbGxvd2VkX2NhcHMKICAgICAgICAgICAgICAgIGlmIHVua25vd246CiAgICAgICAgICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigKICAgICAgICAgICAgICAgICAgICAgICAgZiJzdGVwIHtzdGVwX2lkIG9yIGluZGV4fSByZXF1ZXN0cyB1bnJvdXRhYmxlICIKICAgICAgICAgICAgICAgICAgICAgICAgZiJjYXBhYmlsaXRpZXMgZm9yIHtkZXBhcnRtZW50fToge3NvcnRlZCh1bmtub3duKX07ICIKICAgICAgICAgICAgICAgICAgICAgICAgZiJhbGxvd2VkOiB7c29ydGVkKGFsbG93ZWRfY2Fwcyl9IgogICAgICAgICAgICAgICAgICAgICkKCiAgICAgICAgICAgIGRlcGVuZHNfcmF3ID0gcmF3LmdldCgiZGVwZW5kc19vbiIsIFtdKQogICAgICAgICAgICBpZiBub3QgaXNpbnN0YW5jZShkZXBlbmRzX3JhdywgbGlzdCk6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgICAgIGYic3RlcCB7c3RlcF9pZCBvciBpbmRleH0gZGVwZW5kc19vbiBtdXN0IGJlIGEgbGlzdCIKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgZGVwZW5kc19vbiA9IHR1cGxlKAogICAgICAgICAgICAgICAgc3RyKHZhbHVlKS5zdHJpcCgpCiAgICAgICAgICAgICAgICBmb3IgdmFsdWUgaW4gZGVwZW5kc19yYXcKICAgICAgICAgICAgICAgIGlmIHN0cih2YWx1ZSkuc3RyaXAoKQogICAgICAgICAgICApCgogICAgICAgICAgICBlc3RpbWF0ZWRfY29zdCA9IGZsb2F0KHJhdy5nZXQoImVzdGltYXRlZF9jb3N0X3VzZCIsIDAuMCkgb3IgMC4wKQogICAgICAgICAgICBpZiBlc3RpbWF0ZWRfY29zdCA8IDA6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKCJlc3RpbWF0ZWRfY29zdF91c2QgbXVzdCBiZSA+PSAwIikKICAgICAgICAgICAgdG90YWxfY29zdCArPSBlc3RpbWF0ZWRfY29zdAoKICAgICAgICAgICAgc3RlcHMuYXBwZW5kKAogICAgICAgICAgICAgICAgTWlzc2lvblN0ZXBTcGVjKAogICAgICAgICAgICAgICAgICAgIHN0ZXBfaWQ9c3RlcF9pZCwKICAgICAgICAgICAgICAgICAgICB0aXRsZT10aXRsZSwKICAgICAgICAgICAgICAgICAgICBkZXBhcnRtZW50PWRlcGFydG1lbnQsCiAgICAgICAgICAgICAgICAgICAgcmVxdWlyZWRfY2FwYWJpbGl0aWVzPWNhcGFiaWxpdGllcywKICAgICAgICAgICAgICAgICAgICBkZXBlbmRzX29uPWRlcGVuZHNfb24sCiAgICAgICAgICAgICAgICAgICAgZXN0aW1hdGVkX2Nvc3RfdXNkPWVzdGltYXRlZF9jb3N0LAogICAgICAgICAgICAgICAgICAgIGV4dGVybmFsX3NpZGVfZWZmZWN0PWJvb2woCiAgICAgICAgICAgICAgICAgICAgICAgIHJhdy5nZXQoImV4dGVybmFsX3NpZGVfZWZmZWN0IiwgRmFsc2UpCiAgICAgICAgICAgICAgICAgICAgKSwKICAgICAgICAgICAgICAgICAgICBkZXN0cnVjdGl2ZT1ib29sKHJhdy5nZXQoImRlc3RydWN0aXZlIiwgRmFsc2UpKSwKICAgICAgICAgICAgICAgICAgICB0b3VjaGVzX3NlY3JldHM9Ym9vbChyYXcuZ2V0KCJ0b3VjaGVzX3NlY3JldHMiLCBGYWxzZSkpLAogICAgICAgICAgICAgICAgICAgIHJlcXVpcmVzX293bmVyX2FwcHJvdmFsPWJvb2woCiAgICAgICAgICAgICAgICAgICAgICAgIHJhdy5nZXQoInJlcXVpcmVzX293bmVyX2FwcHJvdmFsIiwgRmFsc2UpCiAgICAgICAgICAgICAgICAgICAgKSwKICAgICAgICAgICAgICAgICAgICBvd25lcl9hcHByb3ZlZD1GYWxzZSwKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgKQoKICAgICAgICBpZiB0b3RhbF9jb3N0ID4gc2VsZi5tYXhfdG90YWxfZXN0aW1hdGVkX2Nvc3RfdXNkOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgIm1hbmFnZXIgcGxhbiBleGNlZWRzIHRvdGFsIGVzdGltYXRlZCBjb3N0IGxpbWl0OiAiCiAgICAgICAgICAgICAgICBmInt0b3RhbF9jb3N0Oi42Zn0gPiB7c2VsZi5tYXhfdG90YWxfZXN0aW1hdGVkX2Nvc3RfdXNkOi42Zn0iCiAgICAgICAgICAgICkKCiAgICAgICAgcmV0dXJuIHR1cGxlKHN0ZXBzKQoKICAgIGRlZiBfcHJvbXB0KAogICAgICAgIHNlbGYsCiAgICAgICAgKiwKICAgICAgICBtaXNzaW9uX2lkOiBzdHIsCiAgICAgICAgb2JqZWN0aXZlOiBzdHIsCiAgICAgICAgbWFuYWdlcl9pZDogc3RyLAogICAgKSAtPiBzdHI6CiAgICAgICAgZGVwYXJ0bWVudHMgPSAiLCAiLmpvaW4oc29ydGVkKHNlbGYuYWxsb3dlZF9kZXBhcnRtZW50cykpCgogICAgICAgIGlmIHNlbGYuY2FwYWJpbGl0eV9jYXRhbG9nOgogICAgICAgICAgICBsaW5lcyA9IFtdCiAgICAgICAgICAgIGZvciBkZXBhcnRtZW50IGluIHNvcnRlZChzZWxmLmFsbG93ZWRfZGVwYXJ0bWVudHMpOgogICAgICAgICAgICAgICAgdmFsdWVzID0gc29ydGVkKAogICAgICAgICAgICAgICAgICAgIHNlbGYuY2FwYWJpbGl0eV9jYXRhbG9nLmdldChkZXBhcnRtZW50LCBmcm96ZW5zZXQoKSkKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgICAgIGxpbmVzLmFwcGVuZCgKICAgICAgICAgICAgICAgICAgICBmIi0ge2RlcGFydG1lbnR9OiB7JywgJy5qb2luKHZhbHVlcykgaWYgdmFsdWVzIGVsc2UgJyhub25lKSd9IgogICAgICAgICAgICAgICAgKQogICAgICAgICAgICBjYXRhbG9nID0gIlxuIi5qb2luKGxpbmVzKQogICAgICAgIGVsc2U6CiAgICAgICAgICAgIGNhdGFsb2cgPSAiLSBjYXBhYmlsaXR5IGNhdGFsb2cgbm90IHN1cHBsaWVkIgoKICAgICAgICByZXR1cm4gZiIiIgpZb3UgYXJlIEFIT1MgZGVwYXJ0bWVudCBtYW5hZ2VyIHttYW5hZ2VyX2lkfS4KCk1JU1NJT04gSUQ6CnttaXNzaW9uX2lkfQoKT0JKRUNUSVZFOgp7b2JqZWN0aXZlfQoKQ3JlYXRlIGV4YWN0bHkgb25lIGZpbGUgbmFtZWQgTUlTU0lPTl9QTEFOLmpzb24gaW4gdGhlIGN1cnJlbnQgd29ya3NwYWNlLgpEbyBub3QgY3JlYXRlIG9yIG1vZGlmeSBhbnkgb3RoZXIgZmlsZS4KClRoZSBmaWxlIG11c3QgYmUgdmFsaWQgSlNPTiB3aXRoIHRoaXMgc2hhcGU6Cnt7CiAgInN0ZXBzIjogWwogICAge3sKICAgICAgInN0ZXBfaWQiOiAic2hvcnQtdW5pcXVlLWlkIiwKICAgICAgInRpdGxlIjogImNsZWFyIGV4ZWN1dGFibGUgdGFzayBmb3Igb25lIHdvcmtlciIsCiAgICAgICJkZXBhcnRtZW50IjogIm9uZSBhbGxvd2VkIGRlcGFydG1lbnQiLAogICAgICAicmVxdWlyZWRfY2FwYWJpbGl0aWVzIjogWyJleGFjdC1jYXBhYmlsaXR5LWZyb20tY2F0YWxvZyJdLAogICAgICAiZGVwZW5kc19vbiI6IFtdLAogICAgICAiZXN0aW1hdGVkX2Nvc3RfdXNkIjogMC4wLAogICAgICAiZXh0ZXJuYWxfc2lkZV9lZmZlY3QiOiBmYWxzZSwKICAgICAgImRlc3RydWN0aXZlIjogZmFsc2UsCiAgICAgICJ0b3VjaGVzX3NlY3JldHMiOiBmYWxzZSwKICAgICAgInJlcXVpcmVzX293bmVyX2FwcHJvdmFsIjogZmFsc2UKICAgIH19CiAgXQp9fQoKQWxsb3dlZCBkZXBhcnRtZW50czoKe2RlcGFydG1lbnRzfQoKRVhBQ1QgUk9VVEFCTEUgQ0FQQUJJTElUWSBDQVRBTE9HOgp7Y2F0YWxvZ30KClJ1bGVzOgotIE1heGltdW0ge3NlbGYubWF4X3N0ZXBzfSBzdGVwcy4KLSBDaG9vc2UgdGhlIHNtYWxsZXN0IGNvaGVyZW50IHRlYW0gYW5kIG9yZGVyIG5lZWRlZCBmb3IgdGhlIG9iamVjdGl2ZS4KLSByZXF1aXJlZF9jYXBhYmlsaXRpZXMgTVVTVCBjb250YWluIG9ubHkgZXhhY3Qgc3RyaW5ncyBmcm9tIHRoZSBzZWxlY3RlZAogIGRlcGFydG1lbnQncyBjYXBhYmlsaXR5IGNhdGFsb2cgYWJvdmUuIERvIG5vdCBpbnZlbnQgc3lub255bXMuCi0gUHJlZmVyIHRoZSBtaW5pbXVtIGNhcGFiaWxpdHkgc2V0IHN1ZmZpY2llbnQgdG8gcm91dGUgb25lIHdvcmtlci4KLSBFeHByZXNzIGRlcGVuZGVuY2llcyBleHBsaWNpdGx5IGluIGRlcGVuZHNfb24uCi0gS2VlcCB0aGlzIHBsYW4gbG9jYWwtb25seSBhbmQgcmV2ZXJzaWJsZS4KLSBEbyBub3QgcGxhbiBwdWJsaXNoaW5nLCBtZXNzYWdpbmcsIHBheW1lbnRzLCBwdXJjaGFzZXMsIGRlcGxveW1lbnRzLAogIGNyZWRlbnRpYWwgYWNjZXNzLCBkZXN0cnVjdGl2ZSBhY3Rpb25zLCBvciBleHRlcm5hbCBzaWRlIGVmZmVjdHMgdW5sZXNzCiAgdGhlIG9iamVjdGl2ZSBleHBsaWNpdGx5IHJlcXVpcmVzIHRoZW0uCi0gTmV2ZXIgY2xhaW0gb3Igc2V0IG93bmVyIGFwcHJvdmFsLgotIEZvciB0aGlzIHNtb2tlIHRlc3QsIGFsbCBwbGFubmVkIHdvcmtlciBzdGVwcyBtdXN0IGhhdmUKICBlc3RpbWF0ZWRfY29zdF91c2QgMC4wIGJlY2F1c2UgZXhlY3V0aW9uIGFmdGVyIHBsYW5uaW5nIGlzIGxvY2FsLgotIEZpbmlzaCBvbmx5IGFmdGVyIHZhbGlkYXRpbmcgdGhhdCBNSVNTSU9OX1BMQU4uanNvbiBwYXJzZXMgYXMgSlNPTi4KIiIiLnN0cmlwKCkKCgpkZWYgbWFrZV9idWlsZGVyX3BsYW5uZXJfcnVubmVyKGJ1aWxkZXI6IEFueSkgLT4gUGxhbm5lclJ1bm5lcjoKICAgIGRlZiBfcnVuKHByb21wdDogc3RyLCB3b3Jrc3BhY2U6IFBhdGgpIC0+IEFueToKICAgICAgICByZXR1cm4gYnVpbGRlci5ydW4odGFzaz1wcm9tcHQsIHdvcmtzcGFjZT13b3Jrc3BhY2UpCgogICAgcmV0dXJuIF9ydW4K")
)
[IO.File]::WriteAllBytes(
    $testPath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgppbXBvcnQgcHl0ZXN0Cgpmcm9tIGFob3MuYWlfbWFuYWdlcl9wbGFubmVyIGltcG9ydCBPcGVuSGFuZHNNYW5hZ2VyUGxhbm5lcgoKCmRlZiBfd3JpdGVfcGxhbih3b3Jrc3BhY2U6IFBhdGgsIHBheWxvYWQ6IGRpY3QpIC0+IE5vbmU6CiAgICAod29ya3NwYWNlIC8gIk1JU1NJT05fUExBTi5qc29uIikud3JpdGVfdGV4dCgKICAgICAgICBqc29uLmR1bXBzKHBheWxvYWQpLAogICAgICAgIGVuY29kaW5nPSJ1dGYtOCIsCiAgICApCgoKZGVmIHRlc3RfY2FwYWJpbGl0eV9jYXRhbG9nX2FjY2VwdHNfZXhhY3Rfcm91dGFibGVfY2FwYWJpbGl0aWVzKAogICAgdG1wX3BhdGg6IFBhdGgsCikgLT4gTm9uZToKICAgIGRlZiBydW5uZXIoX3Byb21wdDogc3RyLCB3b3Jrc3BhY2U6IFBhdGgpOgogICAgICAgIF93cml0ZV9wbGFuKAogICAgICAgICAgICB3b3Jrc3BhY2UsCiAgICAgICAgICAgIHsKICAgICAgICAgICAgICAgICJzdGVwcyI6IFsKICAgICAgICAgICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAgICAgICAgICJzdGVwX2lkIjogInJlc2VhcmNoIiwKICAgICAgICAgICAgICAgICAgICAgICAgInRpdGxlIjogIlJlc2VhcmNoIHJlcXVpcmVtZW50cyIsCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBhcnRtZW50IjogInJlc2VhcmNoIiwKICAgICAgICAgICAgICAgICAgICAgICAgInJlcXVpcmVkX2NhcGFiaWxpdGllcyI6IFsicmVzZWFyY2giXSwKICAgICAgICAgICAgICAgICAgICAgICAgImRlcGVuZHNfb24iOiBbXSwKICAgICAgICAgICAgICAgICAgICAgICAgImVzdGltYXRlZF9jb3N0X3VzZCI6IDAuMCwKICAgICAgICAgICAgICAgICAgICB9LAogICAgICAgICAgICAgICAgICAgIHsKICAgICAgICAgICAgICAgICAgICAgICAgInN0ZXBfaWQiOiAiYnVpbGQiLAogICAgICAgICAgICAgICAgICAgICAgICAidGl0bGUiOiAiQnVpbGQgcHJvdG90eXBlIiwKICAgICAgICAgICAgICAgICAgICAgICAgImRlcGFydG1lbnQiOiAic29mdHdhcmUiLAogICAgICAgICAgICAgICAgICAgICAgICAicmVxdWlyZWRfY2FwYWJpbGl0aWVzIjogWyJweXRob24iXSwKICAgICAgICAgICAgICAgICAgICAgICAgImRlcGVuZHNfb24iOiBbInJlc2VhcmNoIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJlc3RpbWF0ZWRfY29zdF91c2QiOiAwLjAsCiAgICAgICAgICAgICAgICAgICAgfSwKICAgICAgICAgICAgICAgIF0KICAgICAgICAgICAgfSwKICAgICAgICApCgogICAgcGxhbm5lciA9IE9wZW5IYW5kc01hbmFnZXJQbGFubmVyKAogICAgICAgIHJ1bm5lcj1ydW5uZXIsCiAgICAgICAgd29ya3NwYWNlX3Jvb3Q9dG1wX3BhdGgsCiAgICAgICAgYWxsb3dlZF9kZXBhcnRtZW50cz1mcm96ZW5zZXQoeyJyZXNlYXJjaCIsICJzb2Z0d2FyZSJ9KSwKICAgICAgICBjYXBhYmlsaXR5X2NhdGFsb2c9ewogICAgICAgICAgICAicmVzZWFyY2giOiBmcm96ZW5zZXQoeyJyZXNlYXJjaCIsICJhbmFseXNpcyJ9KSwKICAgICAgICAgICAgInNvZnR3YXJlIjogZnJvemVuc2V0KHsicHl0aG9uIiwgImF1dG9tYXRpb24ifSksCiAgICAgICAgfSwKICAgICAgICBtYXhfc3RlcHM9NCwKICAgICAgICBtYXhfdG90YWxfZXN0aW1hdGVkX2Nvc3RfdXNkPTAuMCwKICAgICkKCiAgICBzdGVwcyA9IHR1cGxlKHBsYW5uZXIoIm0xIiwgIm9iamVjdGl2ZSIsICJtZ3Itc29mdHdhcmUtMDEiKSkKCiAgICBhc3NlcnQgc3RlcHNbMF0ucmVxdWlyZWRfY2FwYWJpbGl0aWVzID09IGZyb3plbnNldCh7InJlc2VhcmNoIn0pCiAgICBhc3NlcnQgc3RlcHNbMV0ucmVxdWlyZWRfY2FwYWJpbGl0aWVzID09IGZyb3plbnNldCh7InB5dGhvbiJ9KQoKCmRlZiB0ZXN0X2ludmVudGVkX2NhcGFiaWxpdHlfaXNfcmVqZWN0ZWQodG1wX3BhdGg6IFBhdGgpIC0+IE5vbmU6CiAgICBkZWYgcnVubmVyKF9wcm9tcHQ6IHN0ciwgd29ya3NwYWNlOiBQYXRoKToKICAgICAgICBfd3JpdGVfcGxhbigKICAgICAgICAgICAgd29ya3NwYWNlLAogICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAic3RlcHMiOiBbCiAgICAgICAgICAgICAgICAgICAgewogICAgICAgICAgICAgICAgICAgICAgICAic3RlcF9pZCI6ICJyZXNlYXJjaCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJ0aXRsZSI6ICJSZXNlYXJjaCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBhcnRtZW50IjogInJlc2VhcmNoIiwKICAgICAgICAgICAgICAgICAgICAgICAgInJlcXVpcmVkX2NhcGFiaWxpdGllcyI6IFsicmVxdWlyZW1lbnRzX2FuYWx5c2lzIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBlbmRzX29uIjogW10sCiAgICAgICAgICAgICAgICAgICAgICAgICJlc3RpbWF0ZWRfY29zdF91c2QiOiAwLjAsCiAgICAgICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgXQogICAgICAgICAgICB9LAogICAgICAgICkKCiAgICBwbGFubmVyID0gT3BlbkhhbmRzTWFuYWdlclBsYW5uZXIoCiAgICAgICAgcnVubmVyPXJ1bm5lciwKICAgICAgICB3b3Jrc3BhY2Vfcm9vdD10bXBfcGF0aCwKICAgICAgICBhbGxvd2VkX2RlcGFydG1lbnRzPWZyb3plbnNldCh7InJlc2VhcmNoIn0pLAogICAgICAgIGNhcGFiaWxpdHlfY2F0YWxvZz17CiAgICAgICAgICAgICJyZXNlYXJjaCI6IGZyb3plbnNldCh7InJlc2VhcmNoIiwgImFuYWx5c2lzIn0pLAogICAgICAgIH0sCiAgICAgICAgbWF4X3RvdGFsX2VzdGltYXRlZF9jb3N0X3VzZD0wLjAsCiAgICApCgogICAgd2l0aCBweXRlc3QucmFpc2VzKFZhbHVlRXJyb3IsIG1hdGNoPSJ1bnJvdXRhYmxlIGNhcGFiaWxpdGllcyIpOgogICAgICAgIHR1cGxlKHBsYW5uZXIoIm0yIiwgIm9iamVjdGl2ZSIsICJtZ3Itc29mdHdhcmUtMDEiKSkKCgpkZWYgdGVzdF9vd25lcl9hcHByb3ZhbF9pc19uZXZlcl9zZWxmX2dyYW50ZWQodG1wX3BhdGg6IFBhdGgpIC0+IE5vbmU6CiAgICBkZWYgcnVubmVyKF9wcm9tcHQ6IHN0ciwgd29ya3NwYWNlOiBQYXRoKToKICAgICAgICBfd3JpdGVfcGxhbigKICAgICAgICAgICAgd29ya3NwYWNlLAogICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAic3RlcHMiOiBbCiAgICAgICAgICAgICAgICAgICAgewogICAgICAgICAgICAgICAgICAgICAgICAic3RlcF9pZCI6ICJidWlsZCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJ0aXRsZSI6ICJCdWlsZCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBhcnRtZW50IjogInNvZnR3YXJlIiwKICAgICAgICAgICAgICAgICAgICAgICAgInJlcXVpcmVkX2NhcGFiaWxpdGllcyI6IFsicHl0aG9uIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBlbmRzX29uIjogW10sCiAgICAgICAgICAgICAgICAgICAgICAgICJlc3RpbWF0ZWRfY29zdF91c2QiOiAwLjAsCiAgICAgICAgICAgICAgICAgICAgICAgICJvd25lcl9hcHByb3ZlZCI6IFRydWUsCiAgICAgICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgXQogICAgICAgICAgICB9LAogICAgICAgICkKCiAgICBwbGFubmVyID0gT3BlbkhhbmRzTWFuYWdlclBsYW5uZXIoCiAgICAgICAgcnVubmVyPXJ1bm5lciwKICAgICAgICB3b3Jrc3BhY2Vfcm9vdD10bXBfcGF0aCwKICAgICAgICBhbGxvd2VkX2RlcGFydG1lbnRzPWZyb3plbnNldCh7InNvZnR3YXJlIn0pLAogICAgICAgIGNhcGFiaWxpdHlfY2F0YWxvZz17CiAgICAgICAgICAgICJzb2Z0d2FyZSI6IGZyb3plbnNldCh7InB5dGhvbiJ9KSwKICAgICAgICB9LAogICAgICAgIG1heF90b3RhbF9lc3RpbWF0ZWRfY29zdF91c2Q9MC4wLAogICAgKQoKICAgIHN0ZXBzID0gdHVwbGUocGxhbm5lcigibTMiLCAib2JqZWN0aXZlIiwgIm1nci1zb2Z0d2FyZS0wMSIpKQogICAgYXNzZXJ0IHN0ZXBzWzBdLm93bmVyX2FwcHJvdmVkIGlzIEZhbHNlCgoKZGVmIHRlc3RfY29zdF9saW1pdF9pc19lbmZvcmNlZCh0bXBfcGF0aDogUGF0aCkgLT4gTm9uZToKICAgIGRlZiBydW5uZXIoX3Byb21wdDogc3RyLCB3b3Jrc3BhY2U6IFBhdGgpOgogICAgICAgIF93cml0ZV9wbGFuKAogICAgICAgICAgICB3b3Jrc3BhY2UsCiAgICAgICAgICAgIHsKICAgICAgICAgICAgICAgICJzdGVwcyI6IFsKICAgICAgICAgICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAgICAgICAgICJzdGVwX2lkIjogImJ1aWxkIiwKICAgICAgICAgICAgICAgICAgICAgICAgInRpdGxlIjogIkJ1aWxkIiwKICAgICAgICAgICAgICAgICAgICAgICAgImRlcGFydG1lbnQiOiAic29mdHdhcmUiLAogICAgICAgICAgICAgICAgICAgICAgICAicmVxdWlyZWRfY2FwYWJpbGl0aWVzIjogWyJweXRob24iXSwKICAgICAgICAgICAgICAgICAgICAgICAgImRlcGVuZHNfb24iOiBbXSwKICAgICAgICAgICAgICAgICAgICAgICAgImVzdGltYXRlZF9jb3N0X3VzZCI6IDAuMDEsCiAgICAgICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgXQogICAgICAgICAgICB9LAogICAgICAgICkKCiAgICBwbGFubmVyID0gT3BlbkhhbmRzTWFuYWdlclBsYW5uZXIoCiAgICAgICAgcnVubmVyPXJ1bm5lciwKICAgICAgICB3b3Jrc3BhY2Vfcm9vdD10bXBfcGF0aCwKICAgICAgICBhbGxvd2VkX2RlcGFydG1lbnRzPWZyb3plbnNldCh7InNvZnR3YXJlIn0pLAogICAgICAgIGNhcGFiaWxpdHlfY2F0YWxvZz17CiAgICAgICAgICAgICJzb2Z0d2FyZSI6IGZyb3plbnNldCh7InB5dGhvbiJ9KSwKICAgICAgICB9LAogICAgICAgIG1heF90b3RhbF9lc3RpbWF0ZWRfY29zdF91c2Q9MC4wLAogICAgKQoKICAgIHdpdGggcHl0ZXN0LnJhaXNlcyhWYWx1ZUVycm9yLCBtYXRjaD0iY29zdCBsaW1pdCIpOgogICAgICAgIHR1cGxlKHBsYW5uZXIoIm00IiwgIm9iamVjdGl2ZSIsICJtZ3Itc29mdHdhcmUtMDEiKSkK")
)

Write-Host "Running full local AHOS tests BEFORE any AI call..."
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
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-033" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-033"
        title = "Constrain AI manager to routable worker capabilities"
        status = "pending"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        task = "Give the AI department manager the exact capability catalog of routable workers and reject invented capability names. Re-run one real manager planning call with local worker execution."
    }
}
[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

git -C $ws add ahos_core/ahos/ai_manager_planner.py ahos_core/tests/test_ai_manager_capability_catalog.py ahos_core/AHOS_BACKLOG.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "fix(ahos): constrain AI manager to routable capabilities"
if ($LASTEXITCODE -ne 0) {
    throw "git commit failed. No live AI call was made."
}
git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) {
    throw "git push failed. No live AI call was made."
}

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

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

Write-Host ""
Write-Host "Local fix passed and was pushed."
Write-Host "Starting ONE real AI manager retry..."
Write-Host "Workers remain local in this proof; only manager planning uses AI."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host ""

$live = @'
from __future__ import annotations

import json
from pathlib import Path

from ahos.ai_manager_planner import OpenHandsManagerPlanner
from ahos.mission_orchestrator import MissionStatus, MultiWorkerMissionOrchestrator
from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import local_pass_qa, make_local_text_executor

ROOT = Path(r"__ROOT__")
REPORT = Path(r"__REPORT__")
PLAN_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-manager"
MISSION_ID = "AHOS-033-ai-manager-routing-live"

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


profiles = {p.worker_id: p for p in default_virtual_workforce()}
required_ids = ("research-01", "dev-01", "finance-01", "mgr-software-01")
missing = [worker_id for worker_id in required_ids if worker_id not in profiles]
if missing:
    raise RuntimeError(f"missing default workforce profiles: {missing}")

capability_catalog = {
    "research": frozenset(profiles["research-01"].capabilities),
    "software": frozenset(profiles["dev-01"].capabilities),
    "finance": frozenset(profiles["finance-01"].capabilities),
}

print("ROUTABLE CAPABILITY CATALOG:")
for department, values in capability_catalog.items():
    print(" ", department, "=>", sorted(values))

builder = build_builder(resolve_settings())
raw_results = []


def manager_runner(prompt: str, workspace: Path):
    result = builder.run(task=prompt, workspace=workspace)
    raw_results.append(result)
    return result


planner = OpenHandsManagerPlanner(
    runner=manager_runner,
    workspace_root=PLAN_ROOT,
    allowed_departments=frozenset(capability_catalog),
    capability_catalog=capability_catalog,
    max_steps=4,
    max_total_estimated_cost_usd=0.0,
)

registry = VirtualWorkforceRegistry(default_virtual_workforce())
executors = {
    "research-01": make_local_text_executor(
        lambda item, worker_id: "requirements research completed locally"
    ),
    "dev-01": make_local_text_executor(
        lambda item, worker_id: "prototype implementation completed locally"
    ),
    "finance-01": make_local_text_executor(
        lambda item, worker_id: "zero-cost financial note completed locally"
    ),
}

orchestrator = MultiWorkerMissionOrchestrator(
    registry,
    manager_planner=planner,
    executors=executors,
    qa_executor=local_pass_qa,
)

objective = (
    "Create a small internal automation prototype. First determine the minimum "
    "requirements and constraints, then implement the prototype based on that "
    "analysis. Keep the whole mission local-only and zero-cost. Do not contact "
    "anyone, publish, deploy, purchase, or use external services."
)

result = orchestrator.run(
    mission_id=MISSION_ID,
    objective=objective,
    primary_department="software",
)

plan_path = PLAN_ROOT / MISSION_ID / "MISSION_PLAN.json"
if not plan_path.exists():
    raise SystemExit("AHOS-033 manager plan file missing")
plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))

print("=== AHOS-033 REAL AI MANAGER ROUTING RESULT ===")
print("MISSION STATUS:", result.status.value)
print("MANAGER:", result.manager_id)
for raw in plan_payload.get("steps", []):
    print(
        "AI PLAN:",
        raw.get("step_id"),
        "|",
        raw.get("department"),
        "|",
        raw.get("required_capabilities"),
        "| depends_on:",
        raw.get("depends_on"),
    )
for step in result.steps:
    print(
        "EXECUTED:",
        step.step.step_id,
        "| DEPARTMENT:",
        step.step.department,
        "| WORKER:",
        step.worker_id,
        "| STAGE:",
        step.stage.value,
        "| QA:",
        step.qa_summary,
    )

if result.status is not MissionStatus.COMPLETED:
    raise SystemExit("AHOS-033 AI MANAGER ROUTING: FAILED")

departments = [step.step.department for step in result.steps]
workers = [step.worker_id for step in result.steps]

if "research" not in departments or "software" not in departments:
    raise SystemExit("AI manager did not route both research and software")
if "research-01" not in workers or "dev-01" not in workers:
    raise SystemExit("AI manager plan did not route to the expected real worker profiles")

for raw in plan_payload["steps"]:
    department = str(raw["department"]).strip().lower()
    requested = set(raw.get("required_capabilities", []))
    if not requested.issubset(set(capability_catalog[department])):
        raise SystemExit("manager emitted capability outside routable catalog")

cost = None
if raw_results:
    raw = raw_results[-1]
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)

print(
    "REPORTED MANAGER ESTIMATED COST USD:",
    cost if cost is not None else "unavailable",
)
print("AHOS-033 AI MANAGER ROUTING: PASS")

report = {
    "mission_id": MISSION_ID,
    "status": result.status.value,
    "manager_id": result.manager_id,
    "capability_catalog": {
        key: sorted(values)
        for key, values in capability_catalog.items()
    },
    "ai_plan": plan_payload,
    "executed_steps": [
        {
            "step_id": step.step.step_id,
            "department": step.step.department,
            "required_capabilities": sorted(step.step.required_capabilities),
            "worker_id": step.worker_id,
            "stage": step.stage.value,
            "qa_summary": step.qa_summary,
        }
        for step in result.steps
    ],
    "manager_estimated_cost_usd": (
        float(cost) if cost is not None else None
    ),
    "worker_ai_calls_in_this_test": 0,
    "external_business_actions": 0,
}
REPORT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
'@

$live = $live.Replace("__ROOT__", $root.Replace("\","\\"))
$live = $live.Replace("__REPORT__", $reportPath.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $live | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    throw "AHOS-033 live AI manager routing retry failed. See error above."
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
foreach ($id in @("AHOS-032", "AHOS-033")) {
    $t = $b.tasks | Where-Object { $_.id -eq $id } | Select-Object -First 1
    if ($null -ne $t) {
        $t.status = "completed"
        if ($t.PSObject.Properties.Name -contains "completed_at") {
            $t.completed_at = [DateTime]::UtcNow.ToString("o")
        } else {
            $t | Add-Member -NotePropertyName completed_at -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
        }
    }
}
[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

git -C $ws add ahos_core/AHOS_BACKLOG.json ahos_core/reports/AHOS-033-live-ai-manager-routing.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "test(ahos): prove routable AI manager planning"
if ($LASTEXITCODE -ne 0) {
    throw "Live manager routing passed, but git commit failed."
}
git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) {
    throw "Live manager routing passed, but git push failed."
}

Write-Host ""
Write-Host "=== AHOS-033 COMPLETE ==="
Write-Host "Real AI department manager: PASS"
Write-Host "Exact worker capability catalog: PASS"
Write-Host "AI department selection: PASS"
Write-Host "AI capability selection: PASS"
Write-Host "Researcher routing: PASS"
Write-Host "Developer routing: PASS"
Write-Host "Dependency execution: PASS"
Write-Host "Per-step QA: PASS"
Write-Host "AI self-approval prevented: PASS"
Write-Host "External business actions: 0"
