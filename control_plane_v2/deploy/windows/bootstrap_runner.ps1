$ErrorActionPreference = 'Stop'

$RepoUrl = 'https://github.com/liondabo02/runpod-ltx2'
$RunnerRoot = Join-Path $env:ProgramData 'MiniverseRunner'
$RunnerName = "miniverse-$env:COMPUTERNAME"
$Labels = 'miniverse'

function Assert-Administrator {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'PowerShell must be opened as Administrator.'
    }
}

Assert-Administrator

if (Test-Path (Join-Path $RunnerRoot '.runner')) {
    Write-Host "GitHub Actions runner is already configured at $RunnerRoot"
    if (Test-Path (Join-Path $RunnerRoot 'svc.cmd')) {
        Push-Location $RunnerRoot
        try { & .\svc.cmd start | Out-Host } finally { Pop-Location }
    }
    exit 0
}

$secureToken = Read-Host 'Paste the temporary GitHub runner registration token (it stays only in this PowerShell process)' -AsSecureString
$tokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPtr)
}

if ([string]::IsNullOrWhiteSpace($token)) {
    throw 'Runner registration token is empty.'
}

New-Item -ItemType Directory -Force -Path $RunnerRoot | Out-Null

$release = Invoke-RestMethod -Headers @{ 'User-Agent' = 'Miniverse-Runner-Bootstrap' } -Uri 'https://api.github.com/repos/actions/runner/releases/latest'
$asset = $release.assets | Where-Object { $_.name -match '^actions-runner-win-x64-.*\.zip$' } | Select-Object -First 1
if (-not $asset) {
    throw 'Could not find the latest Windows x64 GitHub Actions runner package.'
}

$zipPath = Join-Path $env:TEMP $asset.name
Write-Host "Downloading $($asset.name)..."
Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $zipPath

Write-Host "Extracting runner to $RunnerRoot..."
Expand-Archive -Path $zipPath -DestinationPath $RunnerRoot -Force
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

Push-Location $RunnerRoot
try {
    Write-Host 'Registering runner for this repository...'
    & .\config.cmd --unattended --url $RepoUrl --token $token --name $RunnerName --labels $Labels --work '_work' --replace --runasservice
    if ($LASTEXITCODE -ne 0) { throw "config.cmd failed with exit code $LASTEXITCODE" }

    if (Test-Path '.\svc.cmd') {
        & .\svc.cmd start | Out-Host
    }
} finally {
    $token = $null
    Pop-Location
}

Write-Host ''
Write-Host 'MINIVERSE RUNNER INSTALLED'
Write-Host "Name:   $RunnerName"
Write-Host "Labels: self-hosted, Windows, X64, $Labels"
Write-Host 'Next: GitHub -> Settings -> Actions -> Runners should show this runner as Idle.'
