param(
    [string]$RootDir = ".\runtime\private\animation-studio\audio\voice-candidates"
)

$ErrorActionPreference = "Stop"

Write-Host "=== STUDIO-006 CORE CAST VOICE FACTORY ==="
Write-Host "Goal: generate age/gender/role-appropriate synthetic voices for the recurring cast."
Write-Host "Flow: Qwen3 VoiceDesign English reference -> Chatterbox Turkish clone."
Write-Host "Per-voice listening: NOT REQUIRED."
Write-Host "Automatic retry: NO."
Write-Host "Existing valid WAVs: SKIPPED, so reruns do not duplicate paid work."
Write-Host "Infants: no adult-like sentence TTS; they remain infant-vocalization/SFX characters."
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

if (-not [System.IO.Path]::IsPathRooted($RootDir)) {
    $RootDir = [System.IO.Path]::GetFullPath((Join-Path $root $RootDir))
}
New-Item -ItemType Directory -Force -Path $RootDir | Out-Null

$qwenEndpoint = "uv0t0j8k1oyc0p"
$chatterboxEndpoint = "pufrhe1ee9mnrj"
$qwenUrl = "https://api.runpod.ai/v2/$qwenEndpoint/runsync"
$chatterboxUrl = "https://api.runpod.ai/v2/$chatterboxEndpoint/runsync"

$headers = @{
    Authorization = "Bearer $($env:RUNPOD_API_KEY)"
    "Content-Type" = "application/json"
}

$ascii = [System.Text.Encoding]::ASCII

function Test-ValidWav([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        if ($bytes.Length -lt 44) { return $false }
        return (
            $ascii.GetString($bytes, 0, 4) -eq "RIFF" -and
            $ascii.GetString($bytes, 8, 4) -eq "WAVE"
        )
    }
    catch {
        return $false
    }
}

$characters = @(
    @{
        id="aden"; name="Aden"; age="3"; gender="girl"; mode="speech"; seed=1703;
        instruct="Fictional preschool-age girl, exactly about three years old. Bright, curious, playful, warm and innocent lead-child energy; naturally small youthful vocal quality, believable three-year-old cadence, cheerful curiosity, soft child resonance, clear enough for children's animation. Never sound like an adult woman. Never use adult falsetto pretending to be a child. Do not imitate or resemble any real person.";
        en="Hello! Would you like to play with me today? I found something wonderful!";
        tr="Merhaba! Bugün benimle oyun oynamak ister misin? Çok güzel bir şey buldum!"
    },
    @{
        id="kaan"; name="Kaan"; age="1"; gender="boy"; mode="early_speech"; seed=1101;
        instruct="Fictional one-year-old toddler boy. Very young tiny child timbre, soft cheerful reactions, early-word cadence, simple spontaneous delivery, little laughs and curious sounds. Never sound like an older child or adult. No adult falsetto. Do not imitate any real person.";
        en="Mama! Look! Ball! Come play!";
        tr="Anne! Bak! Top! Gel oynayalım!"
    },
    @{
        id="esra"; name="Esra"; age="33"; gender="woman"; mode="speech"; seed=3331;
        instruct="Fictional 33-year-old adult woman and mother. Warm, reassuring, calm, affectionate, patient and clear; natural maternal warmth without sounding theatrical. Distinct recurring series voice. Do not imitate any real person.";
        en="Come here, children. We can solve this together calmly.";
        tr="Gelin çocuklar. Bunu birlikte sakin sakin çözebiliriz."
    },
    @{
        id="ahmet"; name="Ahmet"; age="33"; gender="man"; mode="speech"; seed=3332;
        instruct="Fictional 33-year-old adult man and father. Kind, relaxed, grounded, supportive and naturally warm; easy conversational delivery, distinct from the other adult men. Do not imitate any real person.";
        en="That sounds like a good idea. Let's help each other.";
        tr="Bu iyi bir fikir gibi görünüyor. Hadi birbirimize yardım edelim."
    },
    @{
        id="esma"; name="Esma"; age="29"; gender="woman"; mode="speech"; seed=2921;
        instruct="Fictional 29-year-old adult woman and aunt. Friendly, warm, lively but gentle, expressive without exaggeration, youthful adult energy and clear diction. Distinct recurring series voice. Do not imitate any real person.";
        en="I have an idea! We can make this even more fun together.";
        tr="Bir fikrim var! Bunu birlikte daha da eğlenceli yapabiliriz."
    },
    @{
        id="harun"; name="Harun"; age="30"; gender="man"; mode="speech"; seed=3031;
        instruct="Fictional 30-year-old adult man and uncle. Warm, confident, optimistic anchor figure; reassuring, composed, light natural humor and energetic when needed. Distinct recurring series voice. Do not imitate any real person.";
        en="Don't worry. We'll organize everything and find a good solution.";
        tr="Merak etmeyin. Her şeyi düzenleyip güzel bir çözüm bulacağız."
    },
    @{
        id="veysel"; name="Veysel"; age="33"; gender="man"; mode="speech"; seed=3333;
        instruct="Fictional 33-year-old adult man. Friendly, sociable and upbeat with a natural conversational rhythm; energetic but believable, clearly distinct from Harun and Ahmet. Do not imitate any real person.";
        en="Great! Then let's get started and see what happens.";
        tr="Harika! O zaman başlayalım ve bakalım ne olacak."
    },
    @{
        id="oznur"; name="Öznur"; age="31"; gender="woman"; mode="speech"; seed=3131;
        instruct="Fictional 31-year-old adult woman. Warm, composed, friendly and clear with gentle conversational energy; calm confidence and natural family warmth. Do not imitate any real person.";
        en="That sounds lovely. We can do it together.";
        tr="Kulağa çok güzel geliyor. Bunu birlikte yapabiliriz."
    },
    @{
        id="salih"; name="Salih"; age="2"; gender="boy"; mode="early_speech"; seed=2201;
        instruct="Fictional two-year-old toddler boy. Playful, curious, naturally small-child timbre, short simple phrases, believable toddler rhythm and lively reactions. Never sound like an adult or older child. No adult falsetto. Do not imitate any real person.";
        en="Look! A car! I want to play!";
        tr="Bak! Araba! Ben de oynamak istiyorum!"
    },
    @{
        id="medine"; name="Medine"; age="2 months"; gender="girl"; mode="infant_vocalization"; seed=0;
        instruct="Infant vocalization only.";
        en=""; tr=""
    },
    @{
        id="davut"; name="Davut"; age="30"; gender="man"; mode="speech"; seed=3032;
        instruct="Fictional 30-year-old adult man. Good-humored, relaxed and warm with natural comic timing when appropriate; friendly and clearly distinct from the other adult men. Do not imitate any real person.";
        en="Well, that was unexpected! Let's figure it out together.";
        tr="Bu hiç beklediğim gibi olmadı! Hadi birlikte çözelim."
    },
    @{
        id="fatos"; name="Fatoş"; age="30"; gender="woman"; mode="speech"; seed=3033;
        instruct="Fictional 30-year-old adult woman. Friendly, expressive and warm with a natural family tone; lively but not theatrical, clearly distinct from the other women. Do not imitate any real person.";
        en="Come on, everyone. I think this will be a lovely day.";
        tr="Hadi herkes gelsin. Bence bugün çok güzel bir gün olacak."
    },
    @{
        id="emos"; name="Emoş"; age="4"; gender="girl"; mode="speech"; seed=4401;
        instruct="Fictional four-year-old preschool girl. Energetic, confident, playful and naturally youthful; clear preschool cadence, a little more assertive than Aden, but still unmistakably a young child. Never sound adult. No adult falsetto. Do not imitate any real person.";
        en="I know! Let's make a game and do it together!";
        tr="Biliyorum! Hadi oyun yapalım ve birlikte oynayalım!"
    },
    @{
        id="berzan"; name="Berzan"; age="2"; gender="boy"; mode="early_speech"; seed=2202;
        instruct="Fictional two-year-old toddler boy and twin. Bright, impulsive, playful small-child voice, quick curious reactions and short phrases. Keep him distinct from his twin Aras. Never sound adult or school-age. No adult falsetto. Do not imitate any real person.";
        en="Me too! Look! I found it!";
        tr="Ben de! Bak! Buldum!"
    },
    @{
        id="aras"; name="Aras"; age="2"; gender="boy"; mode="early_speech"; seed=2203;
        instruct="Fictional two-year-old toddler boy and twin. Softer, calmer small-child voice with gentle curious reactions and short phrases. Keep him distinct from his twin Berzan. Never sound adult or school-age. No adult falsetto. Do not imitate any real person.";
        en="Wait for me. I want to see too.";
        tr="Beni bekle. Ben de görmek istiyorum."
    },
    @{
        id="ramin"; name="Ramin"; age="1 month"; gender="boy"; mode="infant_vocalization"; seed=0;
        instruct="Infant vocalization only.";
        en=""; tr=""
    }
)

$plannedPaidRequests = 0
foreach ($c in $characters) {
    if ($c.mode -eq "infant_vocalization") { continue }
    $charDir = Join-Path $RootDir $c.id
    $ref = Join-Path $charDir "$($c.id)-qwen3-voicedesign-en-01.wav"
    $tr = Join-Path $charDir "$($c.id)-qwen3-chatterbox-tr-01.wav"
    if (-not (Test-ValidWav $ref)) { $plannedPaidRequests++ }
    if (-not (Test-ValidWav $tr)) { $plannedPaidRequests++ }
}

Write-Host "Recurring characters: $($characters.Count)"
Write-Host "Infant SFX-only characters: 2"
Write-Host "Missing paid generations right now: $plannedPaidRequests"
Write-Host ""
if ($plannedPaidRequests -eq 0) {
    Write-Host "All requested voice files already exist and are valid. No paid request needed."
    exit 0
}

Write-Host "WARNING: this batch can start RunPod GPU workers and incur charges."
Write-Host "Each missing reference/clone is one paid request. There are NO automatic retries."
$approval = Read-Host "Type RUN_ALL to authorize the missing batch"
if ($approval -ne "RUN_ALL") {
    Write-Host "Cancelled. No paid requests were sent."
    exit 0
}
Write-Host "Owner batch approval: CONFIRMED"
Write-Host ""

$manifestCharacters = @()
$completedPaidRequests = 0

foreach ($c in $characters) {
    Write-Host "=== $($c.name) | age $($c.age) | $($c.gender) | $($c.mode) ==="

    if ($c.mode -eq "infant_vocalization") {
        Write-Host "SFX ONLY: sentence TTS intentionally skipped."
        $manifestCharacters += @{
            character_id=$c.id
            display_name=$c.name
            age=$c.age
            gender=$c.gender
            speech_mode=$c.mode
            reference_status="not_applicable"
            turkish_status="not_applicable"
            note="infant coos/babble/laugh/cry SFX only; no adult-like sentence TTS"
        }
        Write-Host ""
        continue
    }

    $charDir = Join-Path $RootDir $c.id
    New-Item -ItemType Directory -Force -Path $charDir | Out-Null
    $refFile = Join-Path $charDir "$($c.id)-qwen3-voicedesign-en-01.wav"
    $trFile = Join-Path $charDir "$($c.id)-qwen3-chatterbox-tr-01.wav"

    if (-not (Test-ValidWav $refFile)) {
        if (Test-Path -LiteralPath $refFile) {
            Remove-Item -LiteralPath $refFile -Force
        }

        $qwenBody = @{
            input = @{
                text = $c.en
                language = "English"
                instruct = $c.instruct
                candidate_id = "$($c.id)-qwen3-voicedesign-en-01"
                seed = [int]$c.seed
                max_new_tokens = 1024
            }
        } | ConvertTo-Json -Depth 8 -Compress

        Write-Host "Paid request: Qwen3 VoiceDesign reference..."
        try {
            $qwenResponse = Invoke-RestMethod -Method Post -Uri $qwenUrl -Headers $headers -Body $qwenBody -TimeoutSec 1200
        }
        catch {
            Write-Host "FAILED at Qwen3 reference for $($c.id). Automatic retry: NO"
            throw
        }

        if ($qwenResponse.status -and $qwenResponse.status -notin @("COMPLETED","SUCCESS")) {
            throw "Qwen3 status for $($c.id): $($qwenResponse.status)"
        }
        if (-not $qwenResponse.output -or $qwenResponse.output.ok -ne $true -or -not $qwenResponse.output.audio_base64) {
            throw "Qwen3 did not return a valid audio payload for $($c.id)."
        }

        $refBytes = [Convert]::FromBase64String([string]$qwenResponse.output.audio_base64)
        [System.IO.File]::WriteAllBytes($refFile, $refBytes)
        if (-not (Test-ValidWav $refFile)) {
            throw "Qwen3 reference for $($c.id) is not valid RIFF/WAVE."
        }
        $completedPaidRequests++
        Write-Host "Reference: PASS"
    }
    else {
        Write-Host "Reference: EXISTING VALID - SKIPPED"
    }

    $refBytes = [System.IO.File]::ReadAllBytes($refFile)
    $refSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $refFile).Hash.ToLowerInvariant()

    if (-not (Test-ValidWav $trFile)) {
        if (Test-Path -LiteralPath $trFile) {
            Remove-Item -LiteralPath $trFile -Force
        }

        $cbBody = @{
            input = @{
                text = $c.tr
                language_id = "tr"
                voice_id = "$($c.id)-qwen3-chatterbox-tr-01"
                reference_audio_base64 = [Convert]::ToBase64String($refBytes)
                allow_builtin_voice = $false
                exaggeration = 0.45
                cfg_weight = 0.55
                temperature = 0.75
            }
        } | ConvertTo-Json -Depth 8 -Compress

        Write-Host "Paid request: Chatterbox Turkish clone..."
        try {
            $cbResponse = Invoke-RestMethod -Method Post -Uri $chatterboxUrl -Headers $headers -Body $cbBody -TimeoutSec 1200
        }
        catch {
            Write-Host "FAILED at Turkish clone for $($c.id). Automatic retry: NO"
            throw
        }

        if ($cbResponse.status -and $cbResponse.status -notin @("COMPLETED","SUCCESS")) {
            throw "Chatterbox status for $($c.id): $($cbResponse.status)"
        }
        if (-not $cbResponse.output -or $cbResponse.output.ok -ne $true -or -not $cbResponse.output.audio_base64) {
            throw "Chatterbox did not return a valid audio payload for $($c.id)."
        }

        $trBytes = [Convert]::FromBase64String([string]$cbResponse.output.audio_base64)
        [System.IO.File]::WriteAllBytes($trFile, $trBytes)
        if (-not (Test-ValidWav $trFile)) {
            throw "Turkish clone for $($c.id) is not valid RIFF/WAVE."
        }
        $completedPaidRequests++
        Write-Host "Turkish clone: PASS"
    }
    else {
        Write-Host "Turkish clone: EXISTING VALID - SKIPPED"
    }

    $trSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $trFile).Hash.ToLowerInvariant()

    $manifestCharacters += @{
        character_id=$c.id
        display_name=$c.name
        age=$c.age
        gender=$c.gender
        speech_mode=$c.mode
        reference_file=$refFile
        reference_sha256=$refSha
        turkish_file=$trFile
        turkish_sha256=$trSha
        reference_status="ready"
        turkish_status="ready"
        generation_policy="age_gender_role_directed"
        per_voice_human_listening_required=$false
        canonical_binding_created=$false
    }

    Write-Host "Character complete: $($c.id)"
    Write-Host ""
}

$manifest = @{
    schema="ahos.core-cast-voice-factory.v1"
    status="batch_generation_complete"
    policy="age_gender_role_directed_with_technical_wav_validation"
    per_voice_human_listening_required=$false
    exception_review="only if generation fails or a later production QA flag is raised"
    paid_requests_completed=$completedPaidRequests
    automatic_retries=0
    qwen_endpoint_id=$qwenEndpoint
    chatterbox_endpoint_id=$chatterboxEndpoint
    canonical_binding_created=$false
    characters=$manifestCharacters
} | ConvertTo-Json -Depth 10

$manifestPath = Join-Path $RootDir "core-cast-voice-factory-manifest.json"
Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding UTF8

Write-Host "=== CORE CAST VOICE FACTORY COMPLETE ==="
Write-Host "Paid requests completed in this run: $completedPaidRequests"
Write-Host "Automatic retries: 0"
Write-Host "Per-voice listening required: NO"
Write-Host "Canonical binding created: NO"
Write-Host "Manifest: $manifestPath"
