param([string]$RuntimeDir = "")
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
Set-Content -Path (Join-Path $RuntimeDir "company-service.stop") -Value "owner stop requested" -Encoding UTF8
Write-Output "AHOS company service stop requested."
