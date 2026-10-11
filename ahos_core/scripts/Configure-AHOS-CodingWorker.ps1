param(
    [string]$RuntimeDir = "",
    [string]$PythonExe = "",
    [ValidateSet("OpenRouter", "Antigravity")]
    [string]$Provider = "OpenRouter",
    [string]$Model = "openrouter/free",
    [string[]]$FallbackModels = @()
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RuntimeDir) { $RuntimeDir = Join-Path $ProjectRoot "runtime" }
if (-not $PythonExe) { $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source }
$RuntimeDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeDir)
$PythonExe = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PythonExe)
$BuilderScript = if ($Provider -eq "Antigravity") {
    Join-Path $ProjectRoot "ahos_core\ahos\antigravity_coding_builder.py"
} else {
    Join-Path $ProjectRoot "ahos_core\ahos\openrouter_coding_builder.py"
}
if (-not (Test-Path -LiteralPath $BuilderScript -PathType Leaf)) {
    throw "Coding builder script is missing: $BuilderScript"
}
if ($Provider -eq "OpenRouter" -and -not $env:OPENROUTER_API_KEY) { throw "OPENROUTER_API_KEY is missing in this PowerShell session" }
[IO.Directory]::CreateDirectory($RuntimeDir) | Out-Null
$BuilderCommand = @($PythonExe, $BuilderScript, "--model", $Model)
if ($Provider -eq "Antigravity") {
    $BuilderCommand = @($PythonExe, $BuilderScript, "--timeout-seconds", "180", "--attempts", "2")
}
foreach ($FallbackModel in $(if ($Provider -eq "OpenRouter") { $FallbackModels } else { @() })) {
    if (-not [string]::IsNullOrWhiteSpace($FallbackModel)) {
        $BuilderCommand += @("--fallback-model", $FallbackModel)
    }
}
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
        builder_command = $BuilderCommand
        allowed_test_executables = @($PythonExe)
    }
}
$ConfigPath = Join-Path $RuntimeDir "company-service-config.json"
if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    $Existing = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    # Keep other departments and existing sandbox/queue settings intact.
    if ($Existing.coding_supervisor) {
        foreach ($Property in $Existing.coding_supervisor.PSObject.Properties) {
            if ($Property.Name -notin @("enabled", "builder_command", "allowed_test_executables")) {
                $Config.coding_supervisor[$Property.Name] = $Property.Value
            }
        }
    }
    $Existing | Add-Member -NotePropertyName coding_supervisor -NotePropertyValue $Config.coding_supervisor -Force
    $Config = $Existing
}
$Json = $Config | ConvertTo-Json -Depth 20
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($ConfigPath, $Json, $Utf8NoBom)
Write-Output "Configured owner-gated $Provider coding worker with persistent supervisor memory: $ConfigPath"
