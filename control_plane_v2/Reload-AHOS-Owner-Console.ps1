param([switch]$Apply)
$ErrorActionPreference='Stop'
$base='http://127.0.0.1:8765'
$sourceRoot=Join-Path (Split-Path $PSScriptRoot -Parent) 'ahos_core'
$stateRoot=Join-Path $sourceRoot 'runtime'
$python='C:\Users\esmak\AppData\Local\Programs\Python\Python312\python.exe'
function Read-IdleState {
    $state=Invoke-RestMethod "$base/api/status" -TimeoutSec 8
    if ($state.growth.running) {throw 'Growth loop running; no process stopped'}
    if (@($state.missions | Where-Object {$_.status -in @('pending','running','queued','retrying')}).Count -gt 0) {throw 'Queue busy; no process stopped'}
    # API only displays the last 50 rows: check the full aggregate too.
    foreach($property in $state.mission_counts.PSObject.Properties){
        if($property.Name -in @('pending','running','queued','retrying') -and $property.Value -gt 0){throw 'Full queue busy; no process stopped'}
    }
    $workerPid=[int](Get-Content -LiteralPath (Join-Path $stateRoot 'control-center.pid'))
    $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$workerPid)
    if(-not $process -or $process.Name -ne 'python.exe' -or $process.CommandLine -notlike '*-m ahos.control_center*' -or $process.CommandLine -notlike ('*'+$stateRoot+'*') -or $process.CommandLine -notlike '*--port 8765*'){throw 'Process identity mismatch'}
    return @{state=$state;pid=$workerPid}
}
$before=Read-IdleState
if(-not $Apply){@{status='IDLE_DRY_RUN';pid=$before.pid}|ConvertTo-Json;return}
$again=Read-IdleState
if($again.pid -ne $before.pid){throw 'Panel process changed; no process stopped'}
$expectedIds=@($before.state.missions.mission_id | Sort-Object)
Stop-Process -Id $before.pid -ErrorAction Stop
$env:PYTHONPATH=$sourceRoot
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
# The reload must not silently enable a cloud provider inherited by this shell.
$env:AHOS_EXECUTOR='local'
$reportRoot=Join-Path $PSScriptRoot 'runtime\owner-panel-reload'
New-Item -ItemType Directory -Force -Path $reportRoot | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$new=Start-Process -FilePath $python -ArgumentList @('-m','ahos.control_center','--runtime-dir',$stateRoot,'--host','127.0.0.1','--port','8765') -WorkingDirectory $sourceRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $reportRoot ($stamp+'.stdout.log')) -RedirectStandardError (Join-Path $reportRoot ($stamp+'.stderr.log'))
$deadline=(Get-Date).AddSeconds(20)
$after=$null
while((Get-Date) -lt $deadline){
    try{$after=Invoke-RestMethod "$base/api/status" -TimeoutSec 2;break}catch{Start-Sleep -Milliseconds 250}
}
if(-not $after){throw 'New panel did not become healthy; inspect reload stderr log'}
$storedPid=[int](Get-Content -LiteralPath (Join-Path $stateRoot 'control-center.pid'))
if($storedPid -ne $new.Id){throw 'New process identity not confirmed'}
$actualIds=@($after.missions.mission_id | Sort-Object)
if(Compare-Object $expectedIds $actualIds){throw 'Visible queue records changed; inspect state'}
$result=@{status='RELOADED_HEALTHY';old_pid=$before.pid;new_pid=$new.Id;preserved_visible_missions=$actualIds.Count;mission_counts=$after.mission_counts;growth=$after.growth;executor='local';model_calls=0}
$result|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $reportRoot ($stamp+'.json')) -Encoding utf8
$result|ConvertTo-Json -Depth 10
