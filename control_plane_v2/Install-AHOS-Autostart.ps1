$ErrorActionPreference = 'Stop'

$Root = (Get-Location).Path

if (-not (Test-Path (Join-Path $Root 'Start-Miniverse.ps1'))) {
    throw "Run this from control_plane_v2. Current path: $Root"
}
if (-not (Test-Path (Join-Path $Root 'Start-Holding-Autopilot.ps1'))) {
    throw "Start-Holding-Autopilot.ps1 not found in: $Root"
}

$StateDir = Join-Path $Root 'runtime\state'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

$LauncherPath = Join-Path $Root 'Start-AHOS-OnLogin.ps1'

$LauncherContent = @'
$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$LogFile = Join-Path $StateDir 'ahos-autostart.log'
$HoldingPidFile = Join-Path $StateDir 'holding-autopilot.pid'

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Write-AutostartLog([string]$Message) {
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $LogFile -Value "[$stamp] $Message"
}

try {
    Write-AutostartLog 'Windows logon launcher started.'

    & (Join-Path $Root 'Start-Miniverse.ps1') *>> $LogFile
    Start-Sleep -Seconds 5

    $holdingRunning = $false
    if (Test-Path $HoldingPidFile) {
        try {
            $holdingPid = [int](Get-Content $HoldingPidFile -Raw)
            if (Get-Process -Id $holdingPid -ErrorAction SilentlyContinue) {
                $holdingRunning = $true
                Write-AutostartLog "AHOS Holding Autopilot already running. PID $holdingPid"
            }
        } catch {}
    }

    if (-not $holdingRunning) {
        & (Join-Path $Root 'Start-Holding-Autopilot.ps1') *>> $LogFile
        Write-AutostartLog 'AHOS Holding Autopilot start command completed.'
    }

    Write-AutostartLog 'Windows logon launcher finished.'
} catch {
    Write-AutostartLog ("AUTOSTART ERROR: " + $_.Exception.Message)
}
'@

Set-Content -Path $LauncherPath -Value $LauncherContent -Encoding utf8

# Validate the generated PowerShell launcher.
[void][scriptblock]::Create((Get-Content $LauncherPath -Raw))

$StartupFolder = [Environment]::GetFolderPath('Startup')
if (-not $StartupFolder) {
    throw 'Windows Startup folder could not be resolved.'
}

$VbsPath = Join-Path $StartupFolder 'AHOS-Autostart.vbs'
$EscapedLauncher = $LauncherPath.Replace('"', '""')

$VbsContent = @"
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""$EscapedLauncher""", 0, False
"@

Set-Content -Path $VbsPath -Value $VbsContent -Encoding ascii

Write-Host ''
Write-Host '=== AHOS AUTOSTART INSTALLED ==='
Write-Host "Launcher: $LauncherPath"
Write-Host "Windows Startup: $VbsPath"
Write-Host ''
Write-Host 'What happens after a reboot:'
Write-Host '1. Sign in to Windows.'
Write-Host '2. Miniverse worker starts hidden in the background.'
Write-Host '3. Holding Autopilot starts if it is not already running.'
Write-Host '4. Budget and per-task safety limits remain in effect.'
Write-Host ''
Write-Host 'Installer made NO OpenAI API calls.'
Write-Host 'Future paid AI work can still occur only when the configured daily budget gate allows it.'
