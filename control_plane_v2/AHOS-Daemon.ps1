#requires -Version 5.1
<#
.SYNOPSIS
  AHOS otonomi dongusunu (bounded scheduler) her zaman acik tutan servis betigi.

.DESCRIPTION
  Panelden bagimsiz, tek ornekli ve gozlenebilir bir surec baslatir.
  Durum dosyasi: <RuntimeDir>\daemon-state.json
  Durdurma: -Action stop (once daemon.stop birakir, sonra gerekirse sureci kapatir)

.EXAMPLE
  .\AHOS-Daemon.ps1 -Action start
  .\AHOS-Daemon.ps1 -Action status
  .\AHOS-Daemon.ps1 -Action stop
#>
param(
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status',

    [string]$RuntimeDir = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime',

    [int]$IntervalSeconds = 60,
    [int]$MissionsPerHour = 6,
    [int]$MissionsTotal = 200,
    [int]$NoEvidenceLimit = 3,
    [int]$PauseCooldownMinutes = 120,
    [string]$LlmBaseUrl = '',
    [string]$LlmModel = 'qwen2.5-coder:7b',
    [string]$LlmApiKey = 'local-only',
    [switch]$LlmFree
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$CoreDir = Join-Path $Root 'ahos_core'
$Python = Join-Path $Root 'control_plane_v2\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

$StateFile = Join-Path $RuntimeDir 'daemon-state.json'
$PidFile = Join-Path $RuntimeDir 'daemon.pid'
$StopFile = Join-Path $RuntimeDir 'daemon.stop'
$OutLog = Join-Path $RuntimeDir 'daemon.out.log'
$ErrLog = Join-Path $RuntimeDir 'daemon.err.log'

# runtime/model.env varsa ortama yükle (API anahtarı komut satırında görünmesin).
$ModelEnv = Join-Path $RuntimeDir 'model.env'
if (Test-Path $ModelEnv) {
    Get-Content $ModelEnv -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim()
        }
    }
}

function Get-DaemonProcess {
    if (-not (Test-Path $PidFile)) { return $null }
    try {
        $meta = Get-Content $PidFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $proc = Get-Process -Id ([int]$meta.pid) -ErrorAction SilentlyContinue
        if (-not $proc) { return $null }
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmd -and $cmd -notmatch 'ahos\.daemon') { return $null }
        return $proc
    } catch {
        return $null
    }
}

function Write-State {
    if (Test-Path $StateFile) {
        $state = Get-Content $StateFile -Raw -Encoding UTF8
        $state
    } else {
        '{"status":"not-running"}'
    }
}

switch ($Action) {
    'start' {
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        Remove-Item $StopFile -ErrorAction SilentlyContinue
        $existing = Get-DaemonProcess
        if ($existing) {
            "zaten calisiyor: pid $($existing.Id)"
            Write-State
            break
        }
        # NOT: surec uzun omurludur; bu betigi bir ajan aracindan cagirmak
        # aracin cikisini bekletir. Baslatma icin Startup .cmd (logon) veya
        # ayri bir terminal kullanin; arac oturumunda arka plan isi + iptal
        # kalibi guvenlidir (surec iptalden sonra yasar).
        $args = @(
            '-m', 'ahos.daemon',
            '--runtime-dir', $RuntimeDir,
            '--interval-seconds', "$IntervalSeconds",
            '--missions-per-hour', "$MissionsPerHour",
            '--missions-total', "$MissionsTotal",
            '--no-evidence-limit', "$NoEvidenceLimit",
            '--pause-cooldown-minutes', "$PauseCooldownMinutes"
        )
        if ($LlmBaseUrl) {
            # Uzak/self-hosted model: RAM kapisi yerel calisma icin; uzak dugumde
            # modeli zorla ve sifir maliyet olarak isaretle.
            $env:AHOS_EXECUTOR = 'model'
            $env:AHOS_LLM_BASE_URL = $LlmBaseUrl
            $env:AHOS_LLM_API_KEY = if ($LlmApiKey) { $LlmApiKey } else { 'local-only' }
            $env:AHOS_LLM_MODEL = $LlmModel
            if ($LlmFree) { $env:AHOS_LLM_FREE = '1' }
            $args += @('--executor-mode', 'model')
        }
        # Uretim politikasi: bir uretim adimi hicbir dosyayi degistirmediyse
        # "tamamlandi" sayilmaz (no_change). Testler istemezse kapatabilir.
        if (-not $env:AHOS_REQUIRE_PRODUCTIVE_CHANGE) {
            $env:AHOS_REQUIRE_PRODUCTIVE_CHANGE = '1'
        }
        $proc = Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $CoreDir `
            -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
        Start-Sleep -Seconds 3
        $started = Get-DaemonProcess
        if ($started) {
            "baslatildi: pid $($started.Id)"
        } else {
            "BASLATILAMADI; hata kaydi: $ErrLog"
        }
        Write-State
    }
    'stop' {
        $proc = Get-DaemonProcess
        if (-not $proc) {
            "calismiyor"
            break
        }
        New-Item -ItemType File -Force -Path $StopFile | Out-Null
        foreach ($i in 1..10) {
            if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 500
        }
        if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
            Stop-Process -Id $proc.Id -Force
            "zorla durduruldu: pid $($proc.Id)"
        } else {
            "durdu: pid $($proc.Id)"
        }
        Remove-Item $StopFile -ErrorAction SilentlyContinue
    }
    'restart' {
        & $PSCommandPath -Action stop -RuntimeDir $RuntimeDir | Out-Null
        Start-Sleep -Seconds 1
        & $PSCommandPath -Action start -RuntimeDir $RuntimeDir -IntervalSeconds $IntervalSeconds `
            -MissionsPerHour $MissionsPerHour -MissionsTotal $MissionsTotal `
            -NoEvidenceLimit $NoEvidenceLimit
    }
    'status' {
        $proc = Get-DaemonProcess
        if ($proc) { "pid: $($proc.Id)" } else { "surec: yok" }
        Write-State
    }
}
