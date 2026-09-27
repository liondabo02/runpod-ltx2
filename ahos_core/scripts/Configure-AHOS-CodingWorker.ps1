param(
    [string]$RuntimeDir = "",
    [string]$PythonExe = "",
    [string]$Model = "openrouter/free"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
if (-not $PythonExe) { $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source }
$RuntimeDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeDir)
$PythonExe = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PythonExe)
$BuilderScript = Join-Path $ProjectRoot "ahos_core\ahos\openrouter_coding_builder.py"
if (-not (Test-Path -LiteralPath $BuilderScript -PathType Leaf)) {
    throw "OpenRouter coding builder script is missing: $BuilderScript"
}
if (-not $env:OPENROUTER_API_KEY) { throw "OPENROUTER_API_KEY is missing in this PowerShell session" }
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
$Config = @{
    coding_supervisor = @{
        enabled = $true
        queue = (Join-Path $RuntimeDir "coding-supervisor-queue.json")
        workspace = (Join-Path $RuntimeDir "coding-worktrees")
        worker_id = "dev-01"
        timeout_seconds = 900
        # Use an absolute script path: the builder runs with the isolated
        # worktree as its current directory, where the ahos package may not be
        # materialized by the Windows scoped checkout.
        builder_command = @($PythonExe, $BuilderScript, "--model", $Model)
        allowed_test_executables = @($PythonExe)
    }
}
$ConfigPath = Join-Path $RuntimeDir "company-service-config.json"
$Json = $Config | ConvertTo-Json -Depth 8
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($ConfigPath, $Json, $Utf8NoBom)
Write-Output "Configured owner-gated OpenRouter coding worker: $ConfigPath"
