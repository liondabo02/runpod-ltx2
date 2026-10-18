param([string]$PythonExe = "", [string]$RuntimeDir = "")
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
$RuntimeDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeDir)
$StatusPath = Join-Path $RuntimeDir "department-service-status.json"
$StopPath = Join-Path $RuntimeDir "department-service.stop"
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
if (Test-Path $StatusPath) {
    $ServiceState = Get-Content $StatusPath -Raw | ConvertFrom-Json
    $DepartmentProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($ServiceState.pid)"
    if ($DepartmentProcess -and $DepartmentProcess.CommandLine -like '*ahos.department_daemon*' -and $DepartmentProcess.CommandLine.Contains($RuntimeDir)) {
        [IO.File]::WriteAllText($StopPath, "requested")
        # Finish any bounded in-flight request; never kill coding or panel processes.
        Wait-Process -Id $ServiceState.pid -Timeout 120 -ErrorAction Stop
    } elseif ($DepartmentProcess) {
        throw "Recorded PID belongs to another process. No process was stopped."
    }
}
& (Join-Path $PSScriptRoot "Start-AHOS-Departments.ps1") -PythonExe $PythonExe -RuntimeDir $RuntimeDir
