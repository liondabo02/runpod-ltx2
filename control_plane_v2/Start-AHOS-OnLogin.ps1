$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root 'runtime\state'
$LogFile = Join-Path $StateDir 'ahos-autostart.log'
$Heartbeat = Join-Path $StateDir 'worker-heartbeat.json'
$HoldingPidFile = Join-Path $StateDir 'holding-autopilot.pid'

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Write-Log([string]$Message) {
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $LogFile -Value "[$stamp] $Message"
}

function Test-WorkerHealthy {
    if (-not (Test-Path $Heartbeat)) { return $false }
    try {
        $h = Get-Content $Heartbeat -Raw | ConvertFrom-Json
        if ($h.state -notin @('polling','running')) { return $false }
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
        $age = $now - [double]$h.timestamp
        return ($age -ge 0 -and $age -le 60)
    } catch {
        return $false
    }
}

Write-Log 'Windows logon launcher started.'

try {
    & (Join-Path $Root 'Start-Miniverse.ps1') *>> $LogFile
} catch {
    Write-Log ("Start-Miniverse warning: " + $_.Exception.Message)
}

$deadline = (Get-Date).AddSeconds(120)
do {
    if ((Get-Process miniverse-worker -ErrorAction SilentlyContinue) -and (Test-WorkerHealthy)) {
        Write-Log 'Miniverse worker is healthy.'
        break
    }
    Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)

if (-not ((Get-Process miniverse-worker -ErrorAction SilentlyContinue) -and (Test-WorkerHealthy))) {
    Write-Log 'AUTOSTART ERROR: worker was not healthy within 120 seconds.'
    exit 1
}

$holdingRunning = $false
if (Test-Path $HoldingPidFile) {
    try {
        $pidValue = [int](Get-Content $HoldingPidFile -Raw)
        if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
            $holdingRunning = $true
            Write-Log "Holding Autopilot already running. PID $pidValue"
        }
    } catch {}
}

if (-not $holdingRunning) {
    try {
        & (Join-Path $Root 'Start-Holding-Autopilot.ps1') *>> $LogFile
        Start-Sleep -Seconds 5
        if (Test-Path $HoldingPidFile) {
            $pidValue = [int](Get-Content $HoldingPidFile -Raw)
            if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
                Write-Log "Holding Autopilot started. PID $pidValue"
            } else {
                Write-Log 'AUTOSTART ERROR: Holding PID exists but process is not running.'
            }
        } else {
            Write-Log 'AUTOSTART ERROR: Holding PID file was not created.'
        }
    } catch {
        Write-Log ("AUTOSTART ERROR starting Holding: " + $_.Exception.Message)
    }
}

Write-Log 'Windows logon launcher finished.'
