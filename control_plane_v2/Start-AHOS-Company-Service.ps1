$ErrorActionPreference='Stop'
Set-Location 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2'
$env:PYTHONPATH='C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\workspaces\ahos-autopilot\ahos_core;C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2'
$python='C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\.venv\Scripts\python.exe'
$stopFile='C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\workspaces\ahos-autopilot\ahos_core\runtime\company-service.stop'
$watchdogPidFile='C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\workspaces\ahos-autopilot\ahos_core\runtime\company-service-watchdog.pid'

# Prevent duplicate watchdogs.
if (Test-Path $watchdogPidFile) {
    try {
        $oldPid = [int](Get-Content $watchdogPidFile -Raw)
        if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
            exit 0
        }
    } catch {}
}
Set-Content -Path $watchdogPidFile -Value $PID -Encoding ascii

$code=@'
from pathlib import Path
from ahos.autonomous_company import CompanyLoop, PersistentMissionQueue
from ahos.company_service import CompanyService
from ahos.mission_orchestrator import MissionResult, MissionStatus
db=Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\workspaces\ahos-autopilot\ahos_core\runtime\company-service.db")
heartbeat=Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\workspaces\ahos-autopilot\ahos_core\runtime\company-service-heartbeat.json")
stop=Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\workspaces\ahos-autopilot\ahos_core\runtime\company-service.stop")
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

try {
    while (-not (Test-Path $stopFile)) {
        $code | & $python -
        if (Test-Path $stopFile) { break }
        Start-Sleep -Seconds 3
    }
}
finally {
    Remove-Item $watchdogPidFile -Force -ErrorAction SilentlyContinue
}