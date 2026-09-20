param([string]$VoiceRoot = ".\\runtime\\private\\animation-studio\\audio\\voice-candidates\\natural-v2")
$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 CORE CAST AUTO VOICE FACTORY ==="
Write-Host "Natural Turkish v2: all speaking characters regenerated in an isolated candidate set."
Write-Host "Existing canonical WAVs are preserved; candidate WAVs are never auto-enrolled."
Write-Host "Existing valid natural-v2 WAVs are skipped; automatic retries disabled."

$root = $PSScriptRoot
$repoRoot = Split-Path -Parent $root
$envFile = Join-Path $root ".env.runtime"
if (-not (Test-Path $envFile)) { throw ".env.runtime not found: $envFile" }

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"').Trim("'"), "Process")
    }
}
if (-not $env:RUNPOD_API_KEY) { throw "RUNPOD_API_KEY missing from .env.runtime" }

if (-not [IO.Path]::IsPathRooted($VoiceRoot)) {
    $VoiceRoot = [IO.Path]::GetFullPath((Join-Path $root $VoiceRoot))
}
New-Item -ItemType Directory -Force -Path $VoiceRoot | Out-Null

$planJson = (& git -C $repoRoot show "origin/feature/ahos-autopilot:ahos_core/config/core-cast-voice-production-plan.json" | Out-String)
if (-not $planJson.Trim()) { throw "Voice production plan could not be loaded from origin/feature/ahos-autopilot" }
$plan = $planJson | ConvertFrom-Json

$qwenUrl = "https://api.runpod.ai/v2/uv0t0j8k1oyc0p/runsync"
$cbUrl = "https://api.runpod.ai/v2/pufrhe1ee9mnrj/runsync"
$headers = @{ Authorization = "Bearer $($env:RUNPOD_API_KEY)"; "Content-Type" = "application/json" }
$ascii = [Text.Encoding]::ASCII

function Test-Wav([string]$Path) {
    if (-not (Test-Path $Path)) { return $false }
    try {
        $b = [IO.File]::ReadAllBytes($Path)
        return $b.Length -ge 44 -and $ascii.GetString($b,0,4) -eq "RIFF" -and $ascii.GetString($b,8,4) -eq "WAVE"
    } catch { return $false }
}

function Save-Wav([string]$Path, [string]$Encoded, [string]$Label) {
    [IO.File]::WriteAllBytes($Path, [Convert]::FromBase64String($Encoded))
    if (-not (Test-Wav $Path)) { throw "$Label returned invalid WAV" }
}

function Voice-Instruct($c) {
    $age = [double]$c.age_years
    $g = [string]$c.gender
    $d = [string]$c.direction
    if ($age -lt 1.5) {
        return "Fictional $g toddler around one year old. Very young child timbre, tiny vocal tract, natural toddler cadence, short early words and simple sounds. Never sound like an adult or adult falsetto. Do not imitate a real person. Character direction: $d."
    }
    if ($age -lt 3) {
        return "Fictional $g toddler about $age years old. Natural small-child timbre, short phrases, believable toddler rhythm. No adult timbre or adult falsetto. Do not imitate a real person. Character direction: $d."
    }
    if ($age -le 5) {
        return "Fictional preschool-age $g child about $age years old. Natural small youthful vocal quality and believable child cadence. Never sound like an adult or adult falsetto. Do not imitate a real person. Character direction: $d."
    }
    return "Fictional $([int]$age)-year-old adult $g voice for role $($c.role). Natural age-appropriate adult timbre, clear diction, distinct recurring identity. Do not imitate a real person. Character direction: $d."
}

# Natural-v2 deliberately does not reuse any earlier candidate, including Aden.
# Every speaking character receives a fresh reference and Turkish render.
$speaking = @($plan.characters | Where-Object { $_.speech_mode -ne "infant_vocalization" })
$missingRef = @()
$missingTr = @()
foreach ($c in $speaking) {
    $dir = Join-Path $VoiceRoot $c.id
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if (-not (Test-Wav (Join-Path $dir "reference-en.wav"))) { $missingRef += $c }
    if (-not (Test-Wav (Join-Path $dir "tr.wav"))) { $missingTr += $c }
}

$maxRequests = $missingRef.Count + $missingTr.Count
Write-Host ""
Write-Host "Speaking characters: $($speaking.Count)"
Write-Host "Infant SFX-only: Medine, Ramin"
Write-Host "Missing Qwen3 references: $($missingRef.Count)"
Write-Host "Missing Turkish clones: $($missingTr.Count)"
Write-Host "Maximum paid requests this run: $maxRequests"

if ($maxRequests -gt 0) {
    $ok = Read-Host "Type RUN BATCH to authorize up to $maxRequests paid requests"
    if ($ok -ne "RUN BATCH") { Write-Host "Cancelled. No batch request sent."; exit 0 }
}

foreach ($c in $missingRef) {
    $dir = Join-Path $VoiceRoot $c.id
    $path = Join-Path $dir "reference-en.wav"
    Write-Host "[QWEN3] $($c.name), age $($c.age_years), $($c.gender)"
    $body = @{ input = @{
        text = [string]$c.en_text
        language = "English"
        instruct = Voice-Instruct $c
        candidate_id = "$($c.id)-qwen3-reference-en-v1"
        seed = [int]$c.seed
        max_new_tokens = 1024
    }} | ConvertTo-Json -Depth 8 -Compress
    try { $r = Invoke-RestMethod -Method Post -Uri $qwenUrl -Headers $headers -Body $body -TimeoutSec 1200 }
    catch { Write-Host "FAILED at $($c.name); no retry."; throw }
    if ($r.status -and $r.status -notin @("COMPLETED","SUCCESS")) { throw "Qwen3 status $($r.status)" }
    if (-not $r.output -or $r.output.ok -ne $true -or -not $r.output.audio_base64) { throw "Invalid Qwen3 output for $($c.name)" }
    Save-Wav $path ([string]$r.output.audio_base64) "$($c.name) Qwen3"
}

foreach ($c in $missingTr) {
    $dir = Join-Path $VoiceRoot $c.id
    $refPath = Join-Path $dir "reference-en.wav"
    $trPath = Join-Path $dir "tr.wav"
    if (-not (Test-Wav $refPath)) { throw "Missing reference for $($c.name)" }
    $ref64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($refPath))
    Write-Host "[CHATTERBOX-TR] $($c.name)"
    $body = @{ input = @{
        text = [string]$c.tr_text
        language_id = "tr"
        voice_id = "$($c.id)-tr-v1"
        reference_audio_base64 = $ref64
        allow_builtin_voice = $false
        exaggeration = 0.30
        cfg_weight = 0.35
        temperature = 0.58
    }} | ConvertTo-Json -Depth 8 -Compress
    try { $r = Invoke-RestMethod -Method Post -Uri $cbUrl -Headers $headers -Body $body -TimeoutSec 1200 }
    catch { Write-Host "FAILED at $($c.name); no retry."; throw }
    if ($r.status -and $r.status -notin @("COMPLETED","SUCCESS")) { throw "Chatterbox status $($r.status)" }
    if (-not $r.output -or $r.output.ok -ne $true -or -not $r.output.audio_base64) { throw "Invalid Chatterbox output for $($c.name)" }
    Save-Wav $trPath ([string]$r.output.audio_base64) "$($c.name) Turkish"
}

$rows = @()
foreach ($c in $plan.characters) {
    $dir = Join-Path $VoiceRoot $c.id
    $ref = Join-Path $dir "reference-en.wav"
    $tr = Join-Path $dir "tr.wav"
    $rows += [ordered]@{
        character_id = $c.id
        age_years = $c.age_years
        gender = $c.gender
        speech_mode = $c.speech_mode
        reference_ready = Test-Wav $ref
        turkish_ready = Test-Wav $tr
        individual_listening_required = $true
    }
}
[ordered]@{
    schema = "ahos.core-cast-voice-assets.v1"
    owner_policy = "isolated natural-v2 candidates; human listening approval required before canonical enrollment"
    automatic_retries = 0
    canonical_binding_created = $false
    characters = $rows
} | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $VoiceRoot "core-cast-voice-assets.json") -Encoding UTF8

Write-Host ""
Write-Host "=== CORE CAST AUTO VOICE FACTORY COMPLETE ==="
Write-Host "Voice root: $VoiceRoot"
Write-Host "All speaking characters use newly generated natural-v2 candidates; no previous voice was reused."
Write-Host "Medine and Ramin remain infant-vocalization/SFX only."
Write-Host "Canonical binding remains blocked until owner listening approval. Other languages remain blocked until then."
Write-Host "Automatic retries: 0"
Write-Host "Secret exposed: NO"
