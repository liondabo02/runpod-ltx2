param([string]$VoiceRoot = ".\\runtime\\private\\animation-studio\\audio\\voice-candidates\\natural-v2")
$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 CORE CAST AUTO VOICE FACTORY ==="
Write-Host "Metadata-driven series voices: age + gender + role + character direction."
Write-Host "Owner policy: no per-character audition loop; valid outputs are accepted as production voice assets."
Write-Host "Existing valid WAVs are reused; automatic retries disabled."

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

# Reuse the already owner-approved Aden Qwen3 reference and successful Turkish
# clone so we do not pay for them again. All other valid generated files are
# also reused on reruns.
$speaking = @($plan.characters | Where-Object { $_.speech_mode -ne "infant_vocalization" })

$adenDir = Join-Path $VoiceRoot "aden"
New-Item -ItemType Directory -Force -Path $adenDir | Out-Null
$adenExistingRef = Join-Path $root "runtime\private\animation-studio\audio\voice-candidates\aden\aden-qwen3-voicedesign-en-01.wav"
$adenExistingTr = Join-Path $root "runtime\private\animation-studio\audio\voice-candidates\aden\aden-qwen3-chatterbox-tr-01.wav"
$adenTargetRef = Join-Path $adenDir "reference-en.wav"
$adenTargetTr = Join-Path $adenDir "tr.wav"
if ((Test-Wav $adenExistingRef) -and -not (Test-Wav $adenTargetRef)) {
    Copy-Item -LiteralPath $adenExistingRef -Destination $adenTargetRef -Force
    Write-Host "[Aden] approved Qwen3 reference reused"
}
if ((Test-Wav $adenExistingTr) -and -not (Test-Wav $adenTargetTr)) {
    Copy-Item -LiteralPath $adenExistingTr -Destination $adenTargetTr -Force
    Write-Host "[Aden] successful Turkish clone reused"
}

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
    $ok = Read-Host "Type RUN_ALL to authorize up to $maxRequests paid requests"
    if ($ok -ne "RUN_ALL") { Write-Host "Cancelled. No batch request sent."; exit 0 }
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
        individual_listening_required = $false
        owner_metadata_policy_approved = $true
    }
}
[ordered]@{
    schema = "ahos.core-cast-voice-assets.v1"
    owner_policy = "metadata-driven generation approved by owner; no per-character audition loop"
    automatic_retries = 0
    canonical_binding_created = $false
    ready_for_series_voice_binding = $true
    characters = $rows
} | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $VoiceRoot "core-cast-voice-assets.json") -Encoding UTF8

Write-Host ""
Write-Host "=== CORE CAST AUTO VOICE FACTORY COMPLETE ==="
Write-Host "Voice root: $VoiceRoot"
Write-Host "All speaking characters now have metadata-driven series voice assets when READY=true."
Write-Host "Aden existing approved assets were reused to avoid duplicate paid calls."
Write-Host "Medine and Ramin remain infant-vocalization/SFX only."
Write-Host "Per-character listening loop: DISABLED by owner policy."
Write-Host "Assets are ready for automatic series voice binding after manifest validation."
Write-Host "Automatic retries: 0"
Write-Host "Secret exposed: NO"