param(
    [string]$RepoRoot = "C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2"
)

$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 CHATTERBOX V3 TURKISH LIVE SMOKE TEST ==="
Write-Host "Purpose: exactly ONE paid RunPod TTS request; no automatic retry."
Write-Host "Endpoint: miniverse-chatterbox-v3-prod"
Write-Host "Language: Turkish"
Write-Host ""

$envFile = Join-Path $RepoRoot ".env.runtime"
if (-not (Test-Path $envFile)) {
    throw ".env.runtime not found at $envFile"
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
    $parts = $line.Split("=", 2)
    $name = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if ($name) {
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (-not $env:RUNPOD_API_KEY) {
    throw "RUNPOD_API_KEY is not available in the process environment."
}

$endpointId = "pufrhe1ee9mnrj"
$url = "https://api.runpod.ai/v2/$endpointId/runsync"
$outDir = Join-Path $RepoRoot "runtime\private\animation-studio\audio\samples"
$outFile = Join-Path $outDir "chatterbox-v3-tr-smoke.wav"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$body = @{
    input = @{
        text = "Merhaba. Miniverse çizgi dizi stüdyosu ses sistemi hazır."
        language_id = "tr"
        voice_id = "studio-smoke-tr-v1"
        reference_audio_base64 = $null
        allow_builtin_voice = $true
        exaggeration = 0.5
        cfg_weight = 0.5
        temperature = 0.8
    }
} | ConvertTo-Json -Depth 8

$headers = @{
    Authorization = "Bearer $($env:RUNPOD_API_KEY)"
    "Content-Type" = "application/json"
}

Write-Host "Sending ONE live TTS request..."
$response = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $body -TimeoutSec 900

if ($response.status -and $response.status -notin @("COMPLETED","SUCCESS")) {
    throw "RunPod status: $($response.status)"
}
if (-not $response.output -or $response.output.ok -ne $true) {
    throw "Chatterbox worker did not return ok=true."
}
if (-not $response.output.audio_base64) {
    throw "No audio_base64 returned."
}

$bytes = [Convert]::FromBase64String([string]$response.output.audio_base64)
if ($bytes.Length -lt 44) {
    throw "Audio output is too small."
}

$ascii = [System.Text.Encoding]::ASCII
$riff = $ascii.GetString($bytes, 0, 4)
$wave = $ascii.GetString($bytes, 8, 4)
if ($riff -ne "RIFF" -or $wave -ne "WAVE") {
    throw "Returned bytes are not RIFF/WAVE."
}

[System.IO.File]::WriteAllBytes($outFile, $bytes)
$sha = (Get-FileHash -Algorithm SHA256 $outFile).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "=== STUDIO-006 CHATTERBOX V3 TURKISH LIVE PASS ==="
Write-Host "RunPod status: $($response.status)"
Write-Host "Worker ok: PASS"
Write-Host "Language: $($response.output.language_id)"
Write-Host "RIFF/WAVE signature: PASS"
Write-Host "Audio bytes: $($bytes.Length)"
Write-Host "Sample rate: $($response.output.sample_rate_hz) Hz"
Write-Host "Watermarked: $($response.output.watermarked)"
Write-Host "SHA256: $sha"
Write-Host "Secret exposed: NO"
Write-Host "Automatic retries: 0"
Write-Host "Audio file: $outFile"
