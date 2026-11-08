$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$python = Join-Path $root ".venv\Scripts\python.exe"
$modulePath = Join-Path $pkg "ahos\company_service.py"
$testPath = Join-Path $pkg "tests\test_company_service.py"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$runtimeDir = Join-Path $pkg "runtime"
$heartbeat = Join-Path $runtimeDir "company-service-heartbeat.json"
$stopFile = Join-Path $runtimeDir "company-service.stop"
$launcher = Join-Path $root "Start-AHOS-Company-Service.ps1"
$taskName = "AHOS Company Service"

Write-Host "=== AHOS-037 WINDOWS COMPANY SERVICE ==="
Write-Host "OpenAI API calls: 0"
Write-Host "Paid API spend: USD 0"

[IO.File]::WriteAllBytes($modulePath,[Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KaW1wb3J0IG9zCmltcG9ydCB0aW1lCmZyb20gZGF0YWNsYXNzZXMgaW1wb3J0IGRhdGFjbGFzcwpmcm9tIGRhdGV0aW1lIGltcG9ydCBkYXRldGltZSwgdGltZXpvbmUKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgpmcm9tIC5hdXRvbm9tb3VzX2NvbXBhbnkgaW1wb3J0IENvbXBhbnlMb29wCgoKZGVmIF91dGNfbm93KCkgLT4gc3RyOgogICAgcmV0dXJuIGRhdGV0aW1lLm5vdyh0aW1lem9uZS51dGMpLmlzb2Zvcm1hdCgpCgoKQGRhdGFjbGFzcyhzbG90cz1UcnVlKQpjbGFzcyBDb21wYW55U2VydmljZToKICAgIGxvb3A6IENvbXBhbnlMb29wCiAgICBoZWFydGJlYXRfcGF0aDogUGF0aAogICAgc3RvcF9wYXRoOiBQYXRoCiAgICBwb2xsX3NlY29uZHM6IGZsb2F0ID0gMi4wCgogICAgZGVmIF9fcG9zdF9pbml0X18oc2VsZikgLT4gTm9uZToKICAgICAgICBzZWxmLmhlYXJ0YmVhdF9wYXRoID0gUGF0aChzZWxmLmhlYXJ0YmVhdF9wYXRoKQogICAgICAgIHNlbGYuc3RvcF9wYXRoID0gUGF0aChzZWxmLnN0b3BfcGF0aCkKICAgICAgICBzZWxmLmhlYXJ0YmVhdF9wYXRoLnBhcmVudC5ta2RpcihwYXJlbnRzPVRydWUsIGV4aXN0X29rPVRydWUpCiAgICAgICAgc2VsZi5zdG9wX3BhdGgucGFyZW50Lm1rZGlyKHBhcmVudHM9VHJ1ZSwgZXhpc3Rfb2s9VHJ1ZSkKCiAgICBkZWYgd3JpdGVfaGVhcnRiZWF0KHNlbGYsIHN0YXRlOiBzdHIsICoqZXh0cmE6IG9iamVjdCkgLT4gTm9uZToKICAgICAgICBwYXlsb2FkID0geyJ0aW1lc3RhbXAiOiBfdXRjX25vdygpLCAicGlkIjogb3MuZ2V0cGlkKCksICJzdGF0ZSI6IHN0YXRlLCAqKmV4dHJhfQogICAgICAgIHRtcCA9IHNlbGYuaGVhcnRiZWF0X3BhdGgud2l0aF9zdWZmaXgoc2VsZi5oZWFydGJlYXRfcGF0aC5zdWZmaXggKyAiLnRtcCIpCiAgICAgICAgdG1wLndyaXRlX3RleHQoanNvbi5kdW1wcyhwYXlsb2FkKSwgZW5jb2Rpbmc9InV0Zi04IikKICAgICAgICB0bXAucmVwbGFjZShzZWxmLmhlYXJ0YmVhdF9wYXRoKQoKICAgIGRlZiBzaG91bGRfc3RvcChzZWxmKSAtPiBib29sOgogICAgICAgIHJldHVybiBzZWxmLnN0b3BfcGF0aC5leGlzdHMoKQoKICAgIGRlZiBydW5fb25jZShzZWxmKSAtPiBzdHI6CiAgICAgICAgc2VsZi53cml0ZV9oZWFydGJlYXQoInBvbGxpbmciKQogICAgICAgIG1pc3Npb24gPSBzZWxmLmxvb3AucnVuX29uY2UoKQogICAgICAgIGlmIG1pc3Npb24gaXMgTm9uZToKICAgICAgICAgICAgc2VsZi53cml0ZV9oZWFydGJlYXQoImlkbGUiKQogICAgICAgICAgICByZXR1cm4gImlkbGUiCiAgICAgICAgc2VsZi53cml0ZV9oZWFydGJlYXQoCiAgICAgICAgICAgICJwcm9jZXNzZWQiLAogICAgICAgICAgICBtaXNzaW9uX2lkPW1pc3Npb24ubWlzc2lvbl9pZCwKICAgICAgICAgICAgbWlzc2lvbl9zdGF0dXM9bWlzc2lvbi5zdGF0dXMudmFsdWUsCiAgICAgICAgICAgIGF0dGVtcHRzPW1pc3Npb24uYXR0ZW1wdHMsCiAgICAgICAgKQogICAgICAgIHJldHVybiBtaXNzaW9uLnN0YXR1cy52YWx1ZQoKICAgIGRlZiBydW5fZm9yZXZlcihzZWxmKSAtPiBOb25lOgogICAgICAgIHNlbGYud3JpdGVfaGVhcnRiZWF0KCJzdGFydGluZyIpCiAgICAgICAgd2hpbGUgbm90IHNlbGYuc2hvdWxkX3N0b3AoKToKICAgICAgICAgICAgdHJ5OgogICAgICAgICAgICAgICAgc3RhdGUgPSBzZWxmLnJ1bl9vbmNlKCkKICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBleGM6CiAgICAgICAgICAgICAgICBzZWxmLndyaXRlX2hlYXJ0YmVhdCgiZXJyb3IiLCBlcnJvcj1mInt0eXBlKGV4YykuX19uYW1lX199OiB7ZXhjfSIpCiAgICAgICAgICAgICAgICB0aW1lLnNsZWVwKHNlbGYucG9sbF9zZWNvbmRzKQogICAgICAgICAgICAgICAgY29udGludWUKICAgICAgICAgICAgaWYgc3RhdGUgPT0gImlkbGUiOgogICAgICAgICAgICAgICAgdGltZS5zbGVlcChzZWxmLnBvbGxfc2Vjb25kcykKICAgICAgICBzZWxmLndyaXRlX2hlYXJ0YmVhdCgic3RvcHBlZCIpCg=="))
[IO.File]::WriteAllBytes($testPath,[Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgpmcm9tIGFob3MuYXV0b25vbW91c19jb21wYW55IGltcG9ydCBDb21wYW55TG9vcCwgUGVyc2lzdGVudE1pc3Npb25RdWV1ZQpmcm9tIGFob3MuY29tcGFueV9zZXJ2aWNlIGltcG9ydCBDb21wYW55U2VydmljZQpmcm9tIGFob3MubWlzc2lvbl9vcmNoZXN0cmF0b3IgaW1wb3J0IE1pc3Npb25SZXN1bHQsIE1pc3Npb25TdGF0dXMKCgpkZWYgX2NvbXBsZXRlZChtaXNzaW9uKToKICAgIHJldHVybiBNaXNzaW9uUmVzdWx0KAogICAgICAgIG1pc3Npb25faWQ9bWlzc2lvbi5taXNzaW9uX2lkLAogICAgICAgIG9iamVjdGl2ZT1taXNzaW9uLm9iamVjdGl2ZSwKICAgICAgICBtYW5hZ2VyX2lkPSJtZ3Itc29mdHdhcmUtMDEiLAogICAgICAgIHN0YXR1cz1NaXNzaW9uU3RhdHVzLkNPTVBMRVRFRCwKICAgICAgICBzdGVwcz0oKSwKICAgICAgICByZWFzb249ImRvbmUiLAogICAgKQoKCmRlZiB0ZXN0X3NlcnZpY2Vfd3JpdGVzX2lkbGVfaGVhcnRiZWF0KHRtcF9wYXRoOiBQYXRoKSAtPiBOb25lOgogICAgcXVldWUgPSBQZXJzaXN0ZW50TWlzc2lvblF1ZXVlKHRtcF9wYXRoIC8gIm1pc3Npb25zLmRiIikKICAgIHNlcnZpY2UgPSBDb21wYW55U2VydmljZSgKICAgICAgICBsb29wPUNvbXBhbnlMb29wKHF1ZXVlPXF1ZXVlLCBleGVjdXRvcj1fY29tcGxldGVkKSwKICAgICAgICBoZWFydGJlYXRfcGF0aD10bXBfcGF0aCAvICJoZWFydGJlYXQuanNvbiIsCiAgICAgICAgc3RvcF9wYXRoPXRtcF9wYXRoIC8gInN0b3AiLAogICAgICAgIHBvbGxfc2Vjb25kcz0wLjAxLAogICAgKQogICAgc3RhdGUgPSBzZXJ2aWNlLnJ1bl9vbmNlKCkKICAgIHBheWxvYWQgPSBqc29uLmxvYWRzKCh0bXBfcGF0aCAvICJoZWFydGJlYXQuanNvbiIpLnJlYWRfdGV4dChlbmNvZGluZz0idXRmLTgiKSkKICAgIGFzc2VydCBzdGF0ZSA9PSAiaWRsZSIKICAgIGFzc2VydCBwYXlsb2FkWyJzdGF0ZSJdID09ICJpZGxlIgoKCmRlZiB0ZXN0X3NlcnZpY2VfcHJvY2Vzc2VzX21pc3Npb24odG1wX3BhdGg6IFBhdGgpIC0+IE5vbmU6CiAgICBxdWV1ZSA9IFBlcnNpc3RlbnRNaXNzaW9uUXVldWUodG1wX3BhdGggLyAibWlzc2lvbnMuZGIiKQogICAgcXVldWUuZW5xdWV1ZShtaXNzaW9uX2lkPSJtMSIsIG9iamVjdGl2ZT0ibG9jYWwgbWlzc2lvbiIsIHByaW1hcnlfZGVwYXJ0bWVudD0ic29mdHdhcmUiKQogICAgc2VydmljZSA9IENvbXBhbnlTZXJ2aWNlKAogICAgICAgIGxvb3A9Q29tcGFueUxvb3AocXVldWU9cXVldWUsIGV4ZWN1dG9yPV9jb21wbGV0ZWQpLAogICAgICAgIGhlYXJ0YmVhdF9wYXRoPXRtcF9wYXRoIC8gImhlYXJ0YmVhdC5qc29uIiwKICAgICAgICBzdG9wX3BhdGg9dG1wX3BhdGggLyAic3RvcCIsCiAgICAgICAgcG9sbF9zZWNvbmRzPTAuMDEsCiAgICApCiAgICBzdGF0ZSA9IHNlcnZpY2UucnVuX29uY2UoKQogICAgcGF5bG9hZCA9IGpzb24ubG9hZHMoKHRtcF9wYXRoIC8gImhlYXJ0YmVhdC5qc29uIikucmVhZF90ZXh0KGVuY29kaW5nPSJ1dGYtOCIpKQogICAgYXNzZXJ0IHN0YXRlID09ICJjb21wbGV0ZWQiCiAgICBhc3NlcnQgcGF5bG9hZFsic3RhdGUiXSA9PSAicHJvY2Vzc2VkIgogICAgYXNzZXJ0IHBheWxvYWRbIm1pc3Npb25faWQiXSA9PSAibTEiCgoKZGVmIHRlc3Rfc3RvcF9maWxlX2lzX2hvbm9yZWQodG1wX3BhdGg6IFBhdGgpIC0+IE5vbmU6CiAgICBxdWV1ZSA9IFBlcnNpc3RlbnRNaXNzaW9uUXVldWUodG1wX3BhdGggLyAibWlzc2lvbnMuZGIiKQogICAgc3RvcCA9IHRtcF9wYXRoIC8gInN0b3AiCiAgICBzdG9wLndyaXRlX3RleHQoInN0b3AiLCBlbmNvZGluZz0idXRmLTgiKQogICAgc2VydmljZSA9IENvbXBhbnlTZXJ2aWNlKAogICAgICAgIGxvb3A9Q29tcGFueUxvb3AocXVldWU9cXVldWUsIGV4ZWN1dG9yPV9jb21wbGV0ZWQpLAogICAgICAgIGhlYXJ0YmVhdF9wYXRoPXRtcF9wYXRoIC8gImhlYXJ0YmVhdC5qc29uIiwKICAgICAgICBzdG9wX3BhdGg9c3RvcCwKICAgICAgICBwb2xsX3NlY29uZHM9MC4wMSwKICAgICkKICAgIGFzc2VydCBzZXJ2aWNlLnNob3VsZF9zdG9wKCkgaXMgVHJ1ZQo="))

$old=$env:PYTHONPATH
Push-Location $pkg
$env:PYTHONPATH=$pkg
& $python -m pytest -q
$exit=$LASTEXITCODE
Pop-Location
$env:PYTHONPATH=$old
if($exit -ne 0){ throw "AHOS-037 tests failed." }

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Remove-Item $stopFile -Force -ErrorAction SilentlyContinue

$launcherBody = @"
`$ErrorActionPreference='Stop'
Set-Location '$root'
`$env:PYTHONPATH='$pkg;$root'
`$code=@'
from pathlib import Path
from ahos.autonomous_company import CompanyLoop, PersistentMissionQueue
from ahos.company_service import CompanyService
from ahos.mission_orchestrator import MissionResult, MissionStatus
db=Path(r"$runtimeDir\company-service.db")
heartbeat=Path(r"$heartbeat")
stop=Path(r"$stopFile")
queue=PersistentMissionQueue(db)
def safe_idle_executor(mission):
    return MissionResult(
        mission_id=mission.mission_id,
        objective=mission.objective,
        manager_id="service-safety",
        status=MissionStatus.BLOCKED,
        steps=(),
        reason="AHOS-037 SAFE-IDLE: live AI execution disabled until AHOS-038 approval gate.",
    )
service=CompanyService(
    loop=CompanyLoop(queue=queue,executor=safe_idle_executor,owner="AHOS-WINDOWS-COMPANY-SERVICE"),
    heartbeat_path=heartbeat,
    stop_path=stop,
    poll_seconds=2.0,
)
service.run_forever()
'@
`$code | & '$python' -
"@

[IO.File]::WriteAllText($launcher,$launcherBody,(New-Object System.Text.UTF8Encoding($false)))

# Delete an older task only if it already exists.
$existingTask = & schtasks.exe /Query /TN "$taskName" 2>$null
if ($LASTEXITCODE -eq 0) {
    & schtasks.exe /Delete /TN "$taskName" /F | Out-Null
}

$taskCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
& schtasks.exe /Create /TN "$taskName" /SC ONLOGON /TR "$taskCmd" /RL LIMITED /F | Out-Null
if($LASTEXITCODE -ne 0){ throw "Could not create scheduled task." }

schtasks /Run /TN "$taskName" | Out-Null
Start-Sleep -Seconds 4
if(-not (Test-Path $heartbeat)){ throw "Heartbeat was not created." }

$hb=Get-Content $heartbeat -Raw | ConvertFrom-Json
Write-Host "Heartbeat state:" $hb.state
Write-Host "Heartbeat PID:" $hb.pid

$b=Get-Content $backlogPath -Raw | ConvertFrom-Json
if(-not ($b.tasks | Where-Object {$_.id -eq "AHOS-037"})){
    $b.tasks += [pscustomobject]@{
        id="AHOS-037"; title="Install persistent Windows company service"; status="completed";
        risk="low"; authority="B"; requires_owner_approval=$false;
        completed_at=[DateTime]::UtcNow.ToString("o");
        task="Install a local Windows logon-started company service with heartbeat and SAFE-IDLE mode."
    }
}
[IO.File]::WriteAllText($backlogPath,($b | ConvertTo-Json -Depth 12),(New-Object System.Text.UTF8Encoding($false)))

git -C $ws add ahos_core/ahos/company_service.py ahos_core/tests/test_company_service.py ahos_core/AHOS_BACKLOG.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "feat(ahos): add persistent Windows company service"
if($LASTEXITCODE -ne 0){ throw "git commit failed." }
git -C $ws push origin HEAD
if($LASTEXITCODE -ne 0){ throw "git push failed." }

Write-Host ""
Write-Host "=== AHOS-037 COMPLETE ==="
Write-Host "Full AHOS tests: PASS"
Write-Host "Windows logon task installed: PASS"
Write-Host "Company service started: PASS"
Write-Host "Heartbeat: PASS"
Write-Host "SAFE-IDLE mode: PASS"
Write-Host "OpenAI API calls: 0"
Write-Host "Paid API spend: USD 0"
Write-Host "NEXT: AHOS-038 owner-approval inbox and execution gate."
