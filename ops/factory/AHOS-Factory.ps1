#requires -Version 5.1
<#
.SYNOPSIS
  AHOS fabrikası: bulut işçisini düzenli aralıklarla çalıştırıp outbox'ı doldurur.

.DESCRIPTION
  - SSH tüneli kapalıysa açar (VM'deki Ollama'ya 11500 üzerinden).
  - Ücretsiz model erişilemezse VM'in kendi 3B modelini kullanır.
  - Her turda en fazla N öneri üretir; daemon bunları doğrulayıp uygular.
  - Tek örnek çalışır (pid kilidi), acil durdurma dosyasına saygı duyar.

.EXAMPLE
  .\AHOS-Factory.ps1 -Once
#>
param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$VmIp = '130.61.35.81',
    [string]$KeyPath = "$env:USERPROFILE\.ssh\ahos-quality-99\oracle_ed25519",
    [int]$IntervalMinutes = 20,
    [int]$TasksPerRun = 2,
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
$RuntimeDir = Join-Path $RepoRoot 'ahos_core\runtime'
$PidFile = Join-Path $RuntimeDir 'factory.pid'
$LogFile = Join-Path $RuntimeDir 'factory.log'
$StopFile = Join-Path $RuntimeDir 'autonomy.stop'
$EnvFile = Join-Path $RuntimeDir 'model.env'

function Write-Log([string]$Message) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'), $Message
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Test-Tunnel {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:11500/api/tags' -UseBasicParsing -TimeoutSec 4
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Start-Tunnel {
    if (Test-Tunnel) { return }
    Write-Log 'tünel açılıyor'
    Start-Process -FilePath 'ssh' -ArgumentList @(
        '-i', $KeyPath, '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'ExitOnForwardFailure=yes', '-N',
        '-L', '11500:localhost:11434', "ubuntu@$VmIp"
    ) -WindowStyle Hidden | Out-Null
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Tunnel) { return }
    }
    throw "tünel açılamadı ($VmIp)"
}

function Invoke-Round {
    if (Test-Path $StopFile) { Write-Log 'acil durdurma etkin; tur atlandı'; return }
    Start-Tunnel
    $tasksFile = Join-Path $RuntimeDir 'cloud-tasks.json'
    if (-not (Test-Path $tasksFile)) { Write-Log 'görev listesi yok'; return }
    $env:AHOS_TASKS = $tasksFile
    $env:AHOS_PROJECT = Join-Path $RuntimeDir 'projects\mipiluna'
    $env:AHOS_OUTBOX = Join-Path $RuntimeDir 'cloud-outbox'
    $env:AHOS_LOCAL_URL = 'http://127.0.0.1:11500/v1'
    $env:AHOS_LOCAL_MODEL = 'qwen2.5-coder:3b'
    $env:OPENROUTER_KEY = ''
    $env:AHOS_MAX_TASKS_PER_RUN = "$TasksPerRun"
    $env:AHOS_RUN_BUDGET_SECONDS = '1500'
    $env:AHOS_REQUEST_TIMEOUT = '420'
    $env:PYTHONIOENCODING = 'utf-8'
    $worker = Join-Path $RepoRoot 'ops\cloud\cloud_worker.py'
    $output = & python $worker 2>&1
    Write-Log (($output | Select-Object -Last 4) -join ' | ')
}

if (-not $Once) {
    if (Test-Path $PidFile) {
        $existing = Get-Content $PidFile -Raw
        if ($existing -and (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)) {
            Write-Log "fabrika zaten çalışıyor (pid $existing)"
            exit 0
        }
    }
    Set-Content -Path $PidFile -Value $PID -Encoding ascii
}

try {
    do {
        try { Invoke-Round } catch { Write-Log "tur hatası: $($_.Exception.Message)" }
        if ($Once) { break }
        Start-Sleep -Seconds ($IntervalMinutes * 60)
    } while ($true)
} finally {
    if (-not $Once -and (Test-Path $PidFile)) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
}
