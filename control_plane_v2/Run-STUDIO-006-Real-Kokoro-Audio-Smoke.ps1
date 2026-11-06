$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"
$privateDir = Join-Path $root "runtime\private\animation-studio\audio\samples"
$outWav = Join-Path $privateDir "kokoro-smoke.wav"
$metaJson = Join-Path $privateDir "kokoro-smoke.local.json"

$endpointId = "4vygp64ky68w3z"
$endpointName = "miniverse-kokoro-tts-prod"
$ttsUrl = "https://$endpointId.api.runpod.ai/v1/audio/speech"

Write-Host "=== STUDIO-006 KOKORO REAL AUDIO SMOKE TEST ==="
Write-Host "Purpose: generate ONE tiny real speech sample and validate the WAV bytes."
Write-Host "Requests: exactly 1 live TTS request"
Write-Host "Automatic retry: NO"
Write-Host "A small RunPod charge may occur."
Write-Host ""

function Get-EnvValue([string]$path, [string]$name) {
    if (-not (Test-Path $path)) { return $null }
    $line = Get-Content $path -ErrorAction Stop |
        Where-Object { $_ -match "^\s*$([regex]::Escape($name))\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $null }

    $value = ($line -split "=", 2)[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

$apiKey = $env:RUNPOD_API_KEY
if (-not $apiKey) {
    $apiKey = Get-EnvValue $envRuntime "RUNPOD_API_KEY"
}
if (-not $apiKey) {
    throw "RUNPOD_API_KEY not found."
}

New-Item -ItemType Directory -Force -Path $privateDir | Out-Null

# Idempotence guard: never spend twice if a previously validated sample exists.
if ((Test-Path $outWav) -and (Test-Path $metaJson)) {
    try {
        $prior = Get-Content $metaJson -Raw | ConvertFrom-Json
        if ($prior.validated -eq $true -and $prior.http_status -eq 200) {
            Write-Host "Existing validated sample found."
            Write-Host "No new RunPod request was sent."
            Write-Host "Audio:" $outWav
            exit 0
        }
    } catch {}
}

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "audio/wav"
    "Content-Type" = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

$payload = @{
    model = "tts-1"
    input = "Hello. Miniverse studio is online."
    voice = "af_heart"
    response_format = "wav"
    speed = 1.0
} | ConvertTo-Json -Compress

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Endpoint:" $endpointName
Write-Host "Voice: af_heart"
Write-Host "Format: WAV"
Write-Host "Text length: 34 characters"
Write-Host ""
Write-Host "Sending ONE live TTS request..."

$tmp = "$outWav.part"
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

$status = $null
try {
    $response = Invoke-WebRequest `
        -Uri $ttsUrl `
        -Method Post `
        -Headers $headers `
        -Body $payload `
        -OutFile $tmp `
        -TimeoutSec 330 `
        -UseBasicParsing `
        -PassThru

    $status = [int]$response.StatusCode
}
catch {
    try { $status = [int]$_.Exception.Response.StatusCode } catch {}
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "=== REAL TTS REQUEST FAILED ==="
    if ($status) { Write-Host "HTTP STATUS:" $status }
    Write-Host "ERROR:" $_.Exception.Message
    Write-Host "Automatic retry: NO"
    throw
}

if ($status -ne 200) {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    throw "TTS request returned HTTP $status instead of 200."
}

$bytes = [System.IO.File]::ReadAllBytes($tmp)
if ($bytes.Length -lt 1024) {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    throw "Returned audio is unexpectedly small: $($bytes.Length) bytes."
}

if ($bytes.Length -lt 12) {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    throw "Returned file is too short to be a WAV."
}

$riff = [System.Text.Encoding]::ASCII.GetString($bytes, 0, 4)
$wave = [System.Text.Encoding]::ASCII.GetString($bytes, 8, 4)

if ($riff -ne "RIFF" -or $wave -ne "WAVE") {
    $preview = [System.Text.Encoding]::UTF8.GetString($bytes, 0, [Math]::Min($bytes.Length, 300))
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    Write-Host "Response preview:" $preview
    throw "HTTP 200 was returned, but the body is not a valid RIFF/WAVE file."
}

Move-Item -Path $tmp -Destination $outWav -Force

# Parse WAV properties with Python stdlib; no network/API.
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

$probe = @'
import json, sys, wave
p = sys.argv[1]
with wave.open(p, "rb") as w:
    frames = w.getnframes()
    rate = w.getframerate()
    out = {
        "channels": w.getnchannels(),
        "sample_width_bytes": w.getsampwidth(),
        "sample_rate_hz": rate,
        "frames": frames,
        "duration_seconds": round(frames / rate, 3) if rate else 0,
    }
print(json.dumps(out))
'@

$probePath = Join-Path $env:TEMP "studio006_wav_probe.py"
[IO.File]::WriteAllText($probePath, $probe, [Text.UTF8Encoding]::new($false))
try {
    $probeJson = & $python $probePath $outWav
    if ($LASTEXITCODE -ne 0) { throw "WAV probe failed." }
    $audioInfo = $probeJson | ConvertFrom-Json
}
finally {
    Remove-Item $probePath -Force -ErrorAction SilentlyContinue
}

$sha256 = (Get-FileHash -Path $outWav -Algorithm SHA256).Hash.ToLowerInvariant()

$meta = [ordered]@{
    studio_step = "STUDIO-006 Kokoro real audio smoke test"
    endpoint_name = $endpointName
    endpoint_id = $endpointId
    http_status = 200
    validated = $true
    voice = "af_heart"
    response_format = "wav"
    bytes = $bytes.Length
    sha256 = $sha256
    channels = $audioInfo.channels
    sample_width_bytes = $audioInfo.sample_width_bytes
    sample_rate_hz = $audioInfo.sample_rate_hz
    frames = $audioInfo.frames
    duration_seconds = $audioInfo.duration_seconds
    automatic_retries = 0
    secret_exposed = $false
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
}

$meta | ConvertTo-Json -Depth 5 | Set-Content -Path $metaJson -Encoding UTF8

Write-Host ""
Write-Host "=== STUDIO-006 REAL KOKORO AUDIO PASS ==="
Write-Host "HTTP 200: PASS"
Write-Host "RIFF/WAVE signature: PASS"
Write-Host "Audio bytes:" $bytes.Length
Write-Host "Sample rate:" $audioInfo.sample_rate_hz "Hz"
Write-Host "Channels:" $audioInfo.channels
Write-Host "Duration:" $audioInfo.duration_seconds "seconds"
Write-Host "SHA256:" $sha256
Write-Host "Secret exposed: NO"
Write-Host "Automatic retries: 0"
Write-Host "Audio file:" $outWav
Write-Host ""
Write-Host "NEXT: wire the proven Kokoro provider into AHOS audio_pipeline, then add dubbing/localization."
