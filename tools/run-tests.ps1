# AHOS test koşucusu — her turda/otomatik çalıştırılabilir.
# Kullanım: powershell -NoProfile -ExecutionPolicy Bypass -File tools\run-tests.ps1
# Sonuç: runtime\quality\test-report.txt (özet) + konsol çıktısı
param(
    [string]$Core = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core',
    [string]$Python = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\.venv\Scripts\python.exe',
    [string]$Selection = ''
)

$ErrorActionPreference = 'Continue'
$env:TEMP = "$env:USERPROFILE\AppData\Local\Temp"
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$report = Join-Path $Core 'runtime\quality'
New-Item -ItemType Directory -Force -Path $report | Out-Null
$out = Join-Path $report 'test-report.txt'
$started = Get-Date

Push-Location $Core
try {
    $args = @('-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider', '--tb=line', '--timeout=60')
    if ($Selection) { $args += @('-k', $Selection) }
    $args += 'tests'
    $result = & $Python @args 2>&1
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
$tail = ($result | Select-Object -Last 12) -join "`n"
$summary = ($result | Select-String -Pattern 'passed|failed|error' | Select-Object -Last 1)

$header = @(
    "AHOS test raporu",
    "tarih   : " + $started.ToString('yyyy-MM-dd HH:mm:ss'),
    "süre    : $elapsed s",
    "seçim   : " + $(if ($Selection) { $Selection } else { 'tümü' }),
    "sonuç   : " + $(if ($summary) { $summary.ToString().Trim() } else { 'bilinmiyor' }),
    "çıkış   : $code",
    "",
    "son satırlar:",
    $tail
) -join "`n"

Set-Content -Path $out -Value $header -Encoding utf8
Write-Output $header
exit $code
