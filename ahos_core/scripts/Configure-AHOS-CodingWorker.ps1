param(
    [string]$RuntimeDir = "",
    [string]$PythonExe = "",
    [string]$Model = "openrouter/free"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
if (-not $PythonExe) { $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source }
$RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
$PythonExe = [IO.Path]::GetFullPath($PythonExe)
if (-not $env:OPENROUTER_API_KEY) { throw "OPENROUTER_API_KEY is missing in this PowerShell session" }
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
$Config = @{
    coding_supervisor = @{
        enabled = $true
        queue = (Join-Path $RuntimeDir "coding-supervisor-queue.json")
        workspace = (Join-Path $RuntimeDir "coding-worktrees")
        worker_id = "dev-01"
        timeout_seconds = 900
        builder_command = @($PythonExe, "-m", "ahos.openrouter_coding_builder", "--model", $Model)
        allowed_test_executables = @($PythonExe)
    }
}
$ConfigPath = Join-Path $RuntimeDir "company-service-config.json"
$Config | ConvertTo-Json -Depth 8 | Set-Content -Path $ConfigPath -Encoding utf8
Write-Output "Configured owner-gated OpenRouter coding worker: $ConfigPath"
