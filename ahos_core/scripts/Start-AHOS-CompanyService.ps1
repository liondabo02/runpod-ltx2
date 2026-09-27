param(
    [string]$RuntimeDir = "",
    [string]$PythonExe = ""
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
if (-not $PythonExe) { $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source }
$RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
$StopFile = Join-Path $RuntimeDir "company-service.stop"
Remove-Item $StopFile -Force -ErrorAction SilentlyContinue
$LogFile = Join-Path $RuntimeDir "company-service.log"
$ErrorLog = Join-Path $RuntimeDir "company-service-error.log"
$Arguments = @(
    "-m", "ahos.company_daemon",
    "--runtime-dir", $RuntimeDir,
    "--config", (Join-Path $RuntimeDir "company-service-config.json")
)
Start-Process -FilePath $PythonExe -ArgumentList $Arguments -WorkingDirectory (Join-Path $ProjectRoot "ahos_core") -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLog
Write-Output "AHOS company service start requested: $RuntimeDir"
