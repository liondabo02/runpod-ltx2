param(
    [string]$CandidateDir = ".\runtime\private\animation-studio\audio\voice-candidates\aden"
)

$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 ADEN TURKISH VOICE CANDIDATES ==="
Write-Host "Purpose: create two NEW synthetic candidate speakers and compare them with the already-proven candidate A."
Write-Host "Paid live requests in this run: exactly 4 (2 Kokoro references + 2 Chatterbox Turkish clones)."
Write-Host "Automatic retry: NO"
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

if (-not [System.IO.Path]::IsPathRooted($CandidateDir)) {
    $CandidateDir = [System.IO.Path]::GetFullPath((Join-Path $root $CandidateDir))
}
New-Item -ItemType Directory -Force -Path $CandidateDir | Out-Null

$existingA = Join-Path $root "runtime\private\animation-studio\audio\samples\chatterbox-v3-tr-continuity-smoke.wav"
if (-not (Test-Path -LiteralPath $existingA)) {
    throw "Existing candidate A is missing: $existingA"
}

$ascii = [System.Text.Encoding]::ASCII
function Assert-Wav([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label file not found: $Path"
    }
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 44) {
        throw "$Label WAV is too small."
    }
    if ($ascii.GetString($bytes, 0, 4) -ne "RIFF" -or $ascii.GetString($bytes, 8, 4) -ne "WAVE") {
        throw "$Label is not RIFF/WAVE."
    }
    return $bytes
}

$null = Assert-Wav $existingA "Candidate A"

$kokoroEndpoint = "4vygp64ky68w3z"
$kokoroUrl = "https://$kokoroEndpoint.api.runpod.ai/v1/audio/speech"
$chatterboxEndpoint = "pufrhe1ee9mnrj"
$chatterboxUrl = "https://api.runpod.ai/v2/$chatterboxEndpoint/runsync"

$headers = @{
    Authorization = "Bearer $($env:RUNPOD_API_KEY)"
}

$referenceText = "Hello. We are going on a wonderful adventure together."
$turkishText = "Merhaba. Bugün birlikte güzel bir maceraya çıkıyoruz."

$candidates = @(
    @{
        id = "B"
        source_voice = "af_bella"
        ref_file = (Join-Path $CandidateDir "aden-candidate-b-reference-af_bella.wav")
        out_file = (Join-Path $CandidateDir "aden-candidate-b-tr.wav")
        voice_id = "aden-candidate-b-trial"
    },
    @{
        id = "C"
        source_voice = "am_michael"
        ref_file = (Join-Path $CandidateDir "aden-candidate-c-reference-am_michael.wav")
        out_file = (Join-Path $CandidateDir "aden-candidate-c-tr.wav")
        voice_id = "aden-candidate-c-trial"
    }
)

foreach ($candidate in $candidates) {
    Write-Host ""
    Write-Host "--- Candidate $($candidate.id): synthetic reference $($candidate.source_voice) ---"

    $kokoroBody = @{
        model = "tts-1"
        input = $referenceText
        voice = $candidate.source_voice
        response_format = "wav"
        speed = 1.0
    } | ConvertTo-Json -Compress

    Write-Host "Paid request: Kokoro synthetic reference..."
    $kokoroResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $kokoroUrl -Headers $headers -ContentType "application/json" -Body $kokoroBody -TimeoutSec 600

    if ([int]$kokoroResponse.StatusCode -ne 200) {
        throw "Kokoro HTTP status: $($kokoroResponse.StatusCode)"
    }

    [System.IO.File]::WriteAllBytes($candidate.ref_file, $kokoroResponse.Content)
    $refBytes = Assert-Wav $candidate.ref_file "Candidate $($candidate.id) reference"
    $refSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidate.ref_file).Hash.ToLowerInvariant()

    $chatterboxBody = @{
        input = @{
            text = $turkishText
            language_id = "tr"
            voice_id = $candidate.voice_id
            reference_audio_base64 = [Convert]::ToBase64String($refBytes)
            allow_builtin_voice = $false
            exaggeration = 0.5
            cfg_weight = 0.5
            temperature = 0.8
        }
    } | ConvertTo-Json -Depth 8 -Compress

    Write-Host "Paid request: Chatterbox Turkish clone..."
    $chatterboxResponse = Invoke-RestMethod -Method Post -Uri $chatterboxUrl -Headers $headers -ContentType "application/json" -Body $chatterboxBody -TimeoutSec 900

    if ($chatterboxResponse.status -and $chatterboxResponse.status -notin @("COMPLETED","SUCCESS")) {
        throw "RunPod Chatterbox status: $($chatterboxResponse.status)"
    }
    if (-not $chatterboxResponse.output -or $chatterboxResponse.output.ok -ne $true) {
        throw "Chatterbox worker did not return ok=true for candidate $($candidate.id)."
    }
    if (-not $chatterboxResponse.output.audio_base64) {
        throw "Chatterbox returned no audio_base64 for candidate $($candidate.id)."
    }

    $outBytes = [Convert]::FromBase64String([string]$chatterboxResponse.output.audio_base64)
    [System.IO.File]::WriteAllBytes($candidate.out_file, $outBytes)
    $null = Assert-Wav $candidate.out_file "Candidate $($candidate.id) output"
    $outSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidate.out_file).Hash.ToLowerInvariant()

    Write-Host "Candidate $($candidate.id): PASS"
    Write-Host "Reference SHA256: $refSha"
    Write-Host "Output SHA256: $outSha"
}

$candidateA = [System.IO.Path]::GetFullPath($existingA)
$candidateB = [System.IO.Path]::GetFullPath($candidates[0].out_file)
$candidateC = [System.IO.Path]::GetFullPath($candidates[1].out_file)

$manifest = @{
    character_id = "aden"
    language = "tr"
    status = "human_selection_required"
    canonical_binding_created = $false
    candidate_a = @{
        source = "existing Chatterbox reference-voice proof based on synthetic Kokoro af_heart reference"
        file = $candidateA
    }
    candidate_b = @{
        source = "synthetic Kokoro af_bella -> Chatterbox Multilingual V3 Turkish clone"
        file = $candidateB
    }
    candidate_c = @{
        source = "synthetic Kokoro am_michael -> Chatterbox Multilingual V3 Turkish clone"
        file = $candidateC
    }
    rights_note = "Trial candidates only. Canonical commercial enrollment remains blocked until reference provenance/rights are explicitly confirmed."
} | ConvertTo-Json -Depth 6

$manifestPath = Join-Path $CandidateDir "aden-tr-voice-candidates.json"
Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding UTF8

Write-Host ""
Write-Host "=== ADEN TURKISH VOICE CANDIDATES READY ==="
Write-Host "Candidate A: $candidateA"
Write-Host "Candidate B: $candidateB"
Write-Host "Candidate C: $candidateC"
Write-Host "Manifest: $manifestPath"
Write-Host "Secret exposed: NO"
Write-Host "Automatic retries: 0"
Write-Host "Canonical binding created: NO"
Write-Host ""
Write-Host "Listen A, B, C and choose one. Do not canonically enroll until human selection and rights/provenance approval."