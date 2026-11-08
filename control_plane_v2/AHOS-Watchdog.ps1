#requires -Version 5.1
<#
.SYNOPSIS
  AHOS daemon watchdog: surec olmus veya heartbeat bayatlamissa yeniden baslatir.

.DESCRIPTION
  Otonomi dongusunun "her zaman acik" olmasi, tek bir surecin olmemesine bagli
  degildir. Bu bekci her turda daemon-state.json'i okur; PID yoksa veya son tick
  beklenen araligin 3 katindan eskiyse daemon'i yeniden baslatir ve olayi
  errors.jsonl'a yazar.

.EXAMPLE
  .\AHOS-Watchdog.ps1 -Once
  .\AHOS-Watchdog.ps1 -IntervalSeconds 60
#>
param(
    [string]$RuntimeDir = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime',
    [int]$IntervalSeconds = 60,
    [double]$StaleMultiplier = 3.0,
    [string]$DaemonScriptPath = '',
    [switch]$Once,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$StateFile = Join-Path $RuntimeDir 'daemon-state.json'
$LogFile = Join-Path $RuntimeDir 'watchdog.log'
$DaemonScript = if ($DaemonScriptPath) { $DaemonScriptPath } else { Join-Path $PSScriptRoot 'AHOS-Daemon.ps1' }
$ErrorFile = Join-Path $RuntimeDir 'errors.jsonl'

# Model/modeless yapılandırması: runtime/model.env varsa ortama yükle.
$ModelEnv = Join-Path $RuntimeDir 'model.env'
if (Test-Path $ModelEnv) {
    Get-Content $ModelEnv -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim()
        }
    }
}

function Write-Log([string]$Message) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    if (-not $Quiet) { $line }
}

function Read-Heartbeat {
    if (-not (Test-Path $StateFile)) { return $null }
    try { return Get-Content $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Get-DaemonAlive($State) {
    if (-not $State -or -not $State.pid) { return $false }
    $proc = Get-Process -Id ([int]$State.pid) -ErrorAction SilentlyContinue
    if (-not $proc) { return $false }
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
    if ($cmd -and $cmd -notmatch 'ahos\.daemon') { return $false }
    return $true
}

function Test-Stale($State) {
    if (-not $State -or -not $State.last_tick_at) { return $true }
    try {
        $last = [datetime]::Parse($State.last_tick_at).ToUniversalTime()
    } catch { return $true }
    $age = ([datetime]::UtcNow - $last).TotalSeconds
    $interval = if ($State.interval_seconds) { [double]$State.interval_seconds } else { 60.0 }
    return ($age -gt ($interval * $StaleMultiplier))
}

function Write-ErrorRecord([string]$Reason) {
    $record = @{
        at      = (Get-Date).ToUniversalTime().ToString('o')
        source  = 'watchdog'
        kind    = 'DaemonDown'
        message = $Reason
    } | ConvertTo-Json -Compress
    Add-Content -Path $ErrorFile -Value $record -Encoding utf8
}

function Invoke-Check {
    $state = Read-Heartbeat
    $alive = Get-DaemonAlive $state
    $stale = Test-Stale $state
    if ($alive -and -not $stale) {
        Write-Log ("ok: pid {0}, son tick {1}" -f $state.pid, $state.last_tick_at)
        return $false
    }
    $reason = if (-not $alive) { 'daemon sureci yok' } else { 'heartbeat bayat' }
    Write-Log ("yeniden baslatiliyor: $reason")
    Write-ErrorRecord $reason
    & $DaemonScript -Action start -RuntimeDir $RuntimeDir | Out-Null
    $new = Read-Heartbeat
    if ($new -and $new.pid) { Write-Log ("yeni pid: {0}" -f $new.pid) }
    return $true
}

# Dot-source ise yalniz fonksiyonlari tanimla (birim testi icin).
if ($MyInvocation.InvocationName -eq '.') { return }

if ($Once) {
    Invoke-Check | Out-Null
    exit 0
}

while ($true) {
    try { Invoke-Check | Out-Null } catch { Write-Log ("bekci hatasi: " + $_.Exception.Message) }
    Start-Sleep -Seconds $IntervalSeconds
}
