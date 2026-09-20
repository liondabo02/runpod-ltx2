param(
    [string]$EndpointId = "uv0t0j8k1oyc0p",
    [string]$OutputWav = ".\runtime\private\animation-studio\audio\voice-candidates\aden\aden-qwen3-voicedesign-en-01.wav"
)

$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 QWEN3 ADEN VOICEDESIGN SMOKE ==="
Write-Host "Purpose: create ONE synthetic preschool-age Aden voice reference."
Write-Host "Paid RunPod requests: EXACTLY ONE"
Write-Host "Automatic retry: NO"
Write-Host "Turkish clone: NO (listen to age/character fit first)"
Write-Host "Canonical character binding: NO"
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
Write-Host "Endpoint ID: $EndpointId"

if (-not [System.IO.Path]::IsPathRooted($OutputWav)) {
    $OutputWav = [System.IO.Path]::GetFullPath((Join-Path $root $OutputWav))
}
$outputDir = Split-Path -Parent $OutputWav
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
if (-not (Test-Path -LiteralPath $outputDir)) {
    throw "Output directory could not be prepared: $outputDir"
}

if (Test-Path -LiteralPath $OutputWav) {
    $bytes = [System.IO.File]::ReadAllBytes($OutputWav)
    $ascii = [System.Text.Encoding]::ASCII
    if ($bytes.Length -ge 44 -and
        $ascii.GetString($bytes, 0, 4) -eq "RIFF" -and
        $ascii.GetString($bytes, 8, 4) -eq "WAVE") {
        Write-Host "Existing valid output found. Paid request SKIPPED."
        Write-Host "Output file: $OutputWav"
        exit 0
    }
    Remove-Item -LiteralPath $OutputWav -Force
}

$url = "https://api.runpod.ai/v2/$EndpointId/runsync"
$headers = @{
    Authorization = "Bearer $($env:RUNPOD_API_KEY)"
    "Content-Type" = "application/json"
}

$body = @{
    input = @{
        text = "Hello! Would you like to play with me today? I found something wonderful!"
        language = "English"
        instruct = "Fictional preschool-age girl, about three years old. Bright, playful, warm and innocent; naturally small youthful vocal quality, believable three-year-old cadence, cheerful curiosity, soft child resonance, clear enough for children's animation. Never sound like an adult woman. Never use adult falsetto pretending to be a child. Do not imitate or resemble any real person."
        candidate_id = "aden-qwen3-voicedesign-en-01"
        seed = 1703
        max_new_tokens = 1024
    }
} | ConvertTo-Json -Depth 8 -Compress

Write-Host ""
Write-Host "WARNING: the next request can start a 24 GB RunPod GPU worker and incur usage charges."
Write-Host "Sending ONE paid VoiceDesign request..."

try {
    $response = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $body -TimeoutSec 1200
}
catch {
    Write-Host "VoiceDesign request FAILED. Automatic retry: NO"
    throw
}

if ($response.status -and $response.status -notin @("COMPLETED","SUCCESS")) {
    throw "RunPod status: $($response.status)"
}
if (-not $response.output -or $response.output.ok -ne $true) {
    throw "Qwen3 worker did not return ok=true."
}
if ($response.output.synthetic_voice -ne $true) {
    throw "Worker did not mark output as synthetic_voice=true."
}
if ($response.output.canonical_binding_created -ne $false) {
    throw "Trial generation unexpectedly reports canonical binding."
}
if (-not $response.output.audio_base64) {
    throw "Qwen3 worker returned no audio_base64."
}

$outBytes = [Convert]::FromBase64String([string]$response.output.audio_base64)
$ascii = [System.Text.Encoding]::ASCII
if ($outBytes.Length -lt 44 -or
    $ascii.GetString($outBytes, 0, 4) -ne "RIFF" -or
    $ascii.GetString($outBytes, 8, 4) -ne "WAVE") {
    throw "Output is not a valid RIFF/WAVE file."
}

[System.IO.File]::WriteAllBytes($OutputWav, $outBytes)
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputWav).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "=== QWEN3 ADEN VOICEDESIGN LIVE PASS ==="
Write-Host "RunPod status: $($response.status)"
Write-Host "Worker ok: PASS"
Write-Host "Character target: Aden"
Write-Host "Age target: 3-year-old preschool girl"
Write-Host "Design language: $($response.output.language)"
Write-Host "Synthetic voice: $($response.output.synthetic_voice)"
Write-Host "Canonical binding created: $($response.output.canonical_binding_created)"
Write-Host "RIFF/WAVE signature: PASS"
Write-Host "Audio bytes: $($outBytes.Length)"
Write-Host "Sample rate: $($response.output.sample_rate_hz) Hz"
Write-Host "SHA256: $sha"
Write-Host "Secret exposed: NO"
Write-Host "Automatic retries: 0"
Write-Host "Output file: $OutputWav"
Write-Host ""
Write-Host "NEXT: listen to this English reference. Only if it truly sounds preschool-age will we spend another request cloning it into Turkish with Chatterbox."
