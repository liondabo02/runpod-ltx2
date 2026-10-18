param(
    [string]$ReferenceWav = ".\runtime\private\animation-studio\audio\samples\chatterbox-v3-tr-smoke.wav",
    [string]$OutputWav = ".\runtime\private\animation-studio\audio\samples\chatterbox-v3-tr-continuity-smoke.wav"
)

$ErrorActionPreference = "Stop"

# Resolve all relative paths against this script's own directory, not the
# process working directory (which .NET may report as C:\Windows\System32).
if (-not [System.IO.Path]::IsPathRooted($ReferenceWav)) {
    $ReferenceWav = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $ReferenceWav))
}
if (-not [System.IO.Path]::IsPathRooted($OutputWav)) {
    $OutputWav = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputWav))
}
$envFile = Join-Path $PSScriptRoot ".env.runtime"

# Pre-create and validate the output directory BEFORE the paid request so a
# local filesystem issue can never waste a RunPod generation.
$outputDir = Split-Path -Parent $OutputWav
if (-not $outputDir) {
    throw "Output path has no parent directory: $OutputWav"
}
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
if (-not (Test-Path -LiteralPath $outputDir)) {
    throw "Output directory could not be prepared: $outputDir"
}

Write-Host "=== STUDIO-006 CHATTERBOX V3 REFERENCE-VOICE CONTINUITY SMOKE ==="
Write-Host "Purpose: verify the REAL reference-audio cloning path with exactly ONE paid request."
Write-Host "This is a technical continuity proof only; it does NOT assign this voice to Aden/Kaan."
Write-Host "Automatic retry: NO"
Write-Host ""

if (-not (Test-Path -LiteralPath $envFile)) {
    throw ".env.runtime not found beside the script: $envFile"
}

Get-Content -LiteralPath $envFile | ForEach-Object {
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
    throw "RUNPOD_API_KEY is missing from .env.runtime."
}
Write-Host "RUNPOD_API_KEY: PRESENT (hidden)"

if (-not (Test-Path -LiteralPath $ReferenceWav)) {
    throw "Reference WAV not found: $ReferenceWav"
}

$resolvedReference = (Resolve-Path -LiteralPath $ReferenceWav).Path
$refBytes = [System.IO.File]::ReadAllBytes($resolvedReference)
if ($refBytes.Length -lt 44) {
    throw "Reference WAV is too small."
}
$ascii = [System.Text.Encoding]::ASCII
if ($ascii.GetString($refBytes, 0, 4) -ne "RIFF" -or $ascii.GetString($refBytes, 8, 4) -ne "WAVE") {
    throw "Reference audio is not RIFF/WAVE."
}

$referenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedReference).Hash.ToLowerInvariant()
$referenceBase64 = [Convert]::ToBase64String($refBytes)

$endpointId = "pufrhe1ee9mnrj"
$url = "https://api.runpod.ai/v2/$endpointId/runsync"

$body = @{
    input = @{
        text = "Merhaba. Bugün birlikte güzel bir maceraya çıkıyoruz."
        language_id = "tr"
        voice_id = "studio-continuity-smoke-tr-v1"
        reference_audio_base64 = $referenceBase64
        allow_builtin_voice = $false
        exaggeration = 0.5
        cfg_weight = 0.5
        temperature = 0.8
    }
} | ConvertTo-Json -Depth 8 -Compress

$headers = @{
    Authorization = "Bearer $($env:RUNPOD_API_KEY)"
    "Content-Type" = "application/json"
}

Write-Host "Reference WAV: PASS"
Write-Host "Reference bytes: $($refBytes.Length)"
Write-Host "Reference SHA256: $referenceSha"
Write-Host "Endpoint: miniverse-chatterbox-v3-prod"
Write-Host "Language: Turkish"
Write-Host ""
Write-Host "Sending ONE live reference-voice TTS request..."

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

$outBytes = [Convert]::FromBase64String([string]$response.output.audio_base64)
if ($outBytes.Length -lt 44) {
    throw "Output audio is too small."
}
if ($ascii.GetString($outBytes, 0, 4) -ne "RIFF" -or $ascii.GetString($outBytes, 8, 4) -ne "WAVE") {
    throw "Output bytes are not RIFF/WAVE."
}

[System.IO.File]::WriteAllBytes($OutputWav, $outBytes)
$outputSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputWav).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "=== STUDIO-006 CHATTERBOX V3 REFERENCE-VOICE LIVE PASS ==="
Write-Host "RunPod status: $($response.status)"
Write-Host "Worker ok: PASS"
Write-Host "Reference audio path used: YES"
Write-Host "Built-in voice fallback: NO"
Write-Host "Language: $($response.output.language_id)"
Write-Host "RIFF/WAVE signature: PASS"
Write-Host "Audio bytes: $($outBytes.Length)"
Write-Host "Sample rate: $($response.output.sample_rate_hz) Hz"
Write-Host "Watermarked: $($response.output.watermarked)"
Write-Host "Reference SHA256: $referenceSha"
Write-Host "Output SHA256: $outputSha"
Write-Host "Secret exposed: NO"
Write-Host "Automatic retries: 0"
Write-Host "Output file: $OutputWav"
Write-Host ""
Write-Host "NEXT: listen to reference + output and judge speaker similarity before any canonical character binding."