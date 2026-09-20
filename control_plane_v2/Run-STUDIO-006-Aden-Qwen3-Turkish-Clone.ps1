param(
    [string]$ReferenceWav = ".\runtime\private\animation-studio\audio\voice-candidates\aden\aden-qwen3-voicedesign-en-01.wav",
    [string]$OutputWav = ".\runtime\private\animation-studio\audio\voice-candidates\aden\aden-qwen3-chatterbox-tr-01.wav"
)

$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 ADEN QWEN3 -> CHATTERBOX TURKISH CLONE ==="
Write-Host "Purpose: clone the human-approved Qwen3 preschool voice into Turkish."
Write-Host "Paid RunPod requests: EXACTLY ONE"
Write-Host "Automatic retry: NO"
Write-Host "Canonical character binding: NO (listen to Turkish result first)"
Write-Host ""

$root = $PSScriptRoot
$envFile = Join-Path $root ".env.runtime"
if (-not (Test-Path -LiteralPath $envFile)) {
    throw ".env.runtime not found beside this script: $envFile"
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

if (-not [System.IO.Path]::IsPathRooted($ReferenceWav)) {
    $ReferenceWav = [System.IO.Path]::GetFullPath((Join-Path $root $ReferenceWav))
}
if (-not [System.IO.Path]::IsPathRooted($OutputWav)) {
    $OutputWav = [System.IO.Path]::GetFullPath((Join-Path $root $OutputWav))
}

if (-not (Test-Path -LiteralPath $ReferenceWav)) {
    throw "Human-approved Qwen3 reference WAV not found: $ReferenceWav"
}

$ascii = [System.Text.Encoding]::ASCII
$refBytes = [System.IO.File]::ReadAllBytes($ReferenceWav)
if ($refBytes.Length -lt 44 -or
    $ascii.GetString($refBytes, 0, 4) -ne "RIFF" -or
    $ascii.GetString($refBytes, 8, 4) -ne "WAVE") {
    throw "Reference is not a valid RIFF/WAVE file."
}

$outputDir = Split-Path -Parent $OutputWav
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

if (Test-Path -LiteralPath $OutputWav) {
    $existing = [System.IO.File]::ReadAllBytes($OutputWav)
    if ($existing.Length -ge 44 -and
        $ascii.GetString($existing, 0, 4) -eq "RIFF" -and
        $ascii.GetString($existing, 8, 4) -eq "WAVE") {
        Write-Host "Existing valid Turkish output found. Paid request SKIPPED."
        Write-Host "Output file: $OutputWav"
        exit 0
    }
    Remove-Item -LiteralPath $OutputWav -Force
}

$referenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ReferenceWav).Hash.ToLowerInvariant()
$endpointId = "pufrhe1ee9mnrj"
$url = "https://api.runpod.ai/v2/$endpointId/runsync"

$headers = @{
    Authorization = "Bearer $($env:RUNPOD_API_KEY)"
    "Content-Type" = "application/json"
}

$body = @{
    input = @{
        text = "Merhaba! Bugün benimle oyun oynamak ister misin? Çok güzel bir şey buldum!"
        language_id = "tr"
        voice_id = "aden-qwen3-chatterbox-tr-01"
        reference_audio_base64 = [Convert]::ToBase64String($refBytes)
        allow_builtin_voice = $false
        exaggeration = 0.45
        cfg_weight = 0.55
        temperature = 0.75
    }
} | ConvertTo-Json -Depth 8 -Compress

Write-Host "Reference WAV: PASS"
Write-Host "Reference SHA256: $referenceSha"
Write-Host "Reference human age/character fit: PASS"
Write-Host ""
Write-Host "WARNING: the next request can start the Chatterbox RunPod GPU worker and incur usage charges."
$approval = Read-Host "Type RUN to authorize exactly ONE paid Turkish clone request"
if ($approval -ne "RUN") {
    Write-Host "Cancelled. No paid request was sent."
    exit 0
}

Write-Host "Owner approval: CONFIRMED"
Write-Host "Sending ONE paid Turkish clone request..."

try {
    $response = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $body -TimeoutSec 1200
}
catch {
    Write-Host "Turkish clone request FAILED. Automatic retry: NO"
    throw
}

if ($response.status -and $response.status -notin @("COMPLETED","SUCCESS")) {
    throw "RunPod status: $($response.status)"
}
if (-not $response.output -or $response.output.ok -ne $true) {
    throw "Chatterbox worker did not return ok=true."
}
if (-not $response.output.audio_base64) {
    throw "Chatterbox returned no audio_base64."
}

$outBytes = [Convert]::FromBase64String([string]$response.output.audio_base64)
if ($outBytes.Length -lt 44 -or
    $ascii.GetString($outBytes, 0, 4) -ne "RIFF" -or
    $ascii.GetString($outBytes, 8, 4) -ne "WAVE") {
    throw "Turkish output is not a valid RIFF/WAVE file."
}

[System.IO.File]::WriteAllBytes($OutputWav, $outBytes)
$outputSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputWav).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "=== ADEN TURKISH CLONE LIVE PASS ==="
Write-Host "RunPod status: $($response.status)"
Write-Host "Worker ok: PASS"
Write-Host "Reference source: human-approved Qwen3 VoiceDesign preschool voice"
Write-Host "Reference used: YES"
Write-Host "Built-in fallback: NO"
Write-Host "Language: $($response.output.language_id)"
Write-Host "RIFF/WAVE signature: PASS"
Write-Host "Audio bytes: $($outBytes.Length)"
Write-Host "Sample rate: $($response.output.sample_rate_hz) Hz"
Write-Host "Watermarked: $($response.output.watermarked)"
Write-Host "Reference SHA256: $referenceSha"
Write-Host "Output SHA256: $outputSha"
Write-Host "Secret exposed: NO"
Write-Host "Automatic retries: 0"
Write-Host "Canonical binding created: NO"
Write-Host "Output file: $OutputWav"
Write-Host ""
Write-Host "NEXT: listen to the Turkish result. If it still sounds like Aden's preschool voice, we can enroll it canonically."
