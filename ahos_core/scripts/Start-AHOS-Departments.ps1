param(
    [string]$RuntimeDir = "",
    [string]$PythonExe = ""
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
if (-not $PythonExe) { $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source }
$RuntimeDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeDir)
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
$PersistedKey = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User")
if (-not $env:OPENROUTER_API_KEY -and $PersistedKey) { $env:OPENROUTER_API_KEY = $PersistedKey }
if (-not $env:OPENROUTER_API_KEY) { throw "OPENROUTER_API_KEY is missing in this session and user environment." }
Push-Location (Join-Path $ProjectRoot "ahos_core")
try {
    & $PythonExe -m ahos.department_activation --runtime-dir $RuntimeDir --allow-external
    if ($LASTEXITCODE -ne 0) { throw "Department activation failed." }
    Remove-Item (Join-Path $RuntimeDir "department-service.stop") -Force -ErrorAction SilentlyContinue
    $Arguments = '-m ahos.department_daemon --runtime-dir "' + $RuntimeDir + '"'
    Start-Process -FilePath $PythonExe -ArgumentList $Arguments -WorkingDirectory (Join-Path $ProjectRoot "ahos_core") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeDir "departments.log") -RedirectStandardError (Join-Path $RuntimeDir "departments-error.log")
    Write-Output "Department scheduler start requested. Review Department Work in the restarted panel. Existing coding worker was not stopped."
} finally { Pop-Location }
