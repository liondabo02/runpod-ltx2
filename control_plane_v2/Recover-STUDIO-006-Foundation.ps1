$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$python = Join-Path $root ".venv\Scripts\python.exe"

$skillsRoot = Join-Path $ws ".agents\skills"
$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$audioDb = Join-Path $privateRoot "audio-manifest.db"
$backlogPath = Join-Path $pkg "STUDIO_BACKLOG.json"

Write-Host "=== STUDIO-006 RECOVERY ==="
Write-Host "Cause: backlog helper was called without the required file argument."
Write-Host "The code/tests already passed; this recovery only finishes the interrupted setup."
Write-Host "Live TTS calls: 0"
Write-Host "Paid provider calls: 0"
Write-Host "API spend: USD 0"
Write-Host ""

if (-not (Test-Path $python)) { throw "AHOS Python venv not found." }
if (-not (Test-Path $pkg)) { throw "AHOS package not found." }
if (-not (Test-Path (Join-Path $pkg "ahos\skill_registry.py"))) { throw "skill_registry.py missing." }
if (-not (Test-Path (Join-Path $pkg "ahos\technology_radar.py"))) { throw "technology_radar.py missing." }
if (-not (Test-Path (Join-Path $pkg "ahos\audio_pipeline.py"))) { throw "audio_pipeline.py missing." }

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null

$patchFile = Join-Path $env:TEMP "studio006_recovery_patch.py"

$patchCode = @'
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
task = next((t for t in data["tasks"] if t["id"] == "STUDIO-006"), None)
if task is None:
    raise SystemExit("STUDIO-006 missing")

task["status"] = "in_progress"
task["result"] = (
    "Foundation complete: Agent Skills-compatible Skill Registry, Technology Radar, "
    "provider-agnostic multilingual audio planning, commercial-license gating, "
    "persistent audio manifests, voice continuity and audio QA skills. "
    "Existing Kokoro endpoint remains to be live-wired and verified before STUDIO-006 is complete."
)

path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("STUDIO-006 backlog: IN_PROGRESS")
'@

[IO.File]::WriteAllText($patchFile, $patchCode, [Text.UTF8Encoding]::new($false))

$old = $env:PYTHONPATH
Push-Location $pkg
try {
    $env:PYTHONPATH = $pkg

    Write-Host "Applying backlog recovery..."
    & $python $patchFile $backlogPath
    if ($LASTEXITCODE -ne 0) { throw "STUDIO-006 backlog recovery failed." }

    Write-Host "Validating Agent Skills registry..."
    & $python -c "from ahos.skill_registry import SkillRegistry; r=SkillRegistry(r'$skillsRoot'); s=r.discover_all(); print('SKILLS DISCOVERED:', len(s)); [print(' -', x.name) for x in s]; assert len(s) >= 4"
    if ($LASTEXITCODE -ne 0) { throw "Skill registry validation failed." }

    Write-Host "Validating Technology Radar..."
    & $python -c "from ahos.technology_radar import studio_technology_radar; r=studio_technology_radar(); print('RADAR ENTRIES:', len(r)); [print(' -', x.technology_id, x.status.value) for x in r]; assert len(r) >= 5"
    if ($LASTEXITCODE -ne 0) { throw "Technology Radar validation failed." }

    Write-Host "Initializing/checking persistent private audio manifest..."
    & $python -c "from ahos.audio_pipeline import AudioManifestStore; AudioManifestStore(r'$audioDb'); print('AUDIO MANIFEST DB: READY')"
    if ($LASTEXITCODE -ne 0) { throw "Audio manifest validation failed." }

    Write-Host "Running focused STUDIO-006 tests only..."
    & $python -m pytest `
        tests\test_skill_registry.py `
        tests\test_technology_radar.py `
        tests\test_audio_pipeline.py -q
    if ($LASTEXITCODE -ne 0) { throw "STUDIO-006 focused tests failed." }
}
finally {
    Pop-Location
    $env:PYTHONPATH = $old
    Remove-Item $patchFile -Force -ErrorAction SilentlyContinue
}

# Private runtime files must never be staged.
git -C $ws add `
    ahos_core/ahos/skill_registry.py `
    ahos_core/ahos/technology_radar.py `
    ahos_core/ahos/audio_pipeline.py `
    ahos_core/tests/test_skill_registry.py `
    ahos_core/tests/test_technology_radar.py `
    ahos_core/tests/test_audio_pipeline.py `
    ahos_core/STUDIO_BACKLOG.json `
    .agents/skills

$staged = git -C $ws diff --cached --name-only
if ($staged -match "technology-radar\.local|audio-manifest\.db|runtime\\private|runtime/private") {
    throw "Privacy guard failed: private STUDIO-006 data was staged."
}

if ($staged) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" `
        commit -m "feat(studio): add skill-native multilingual audio foundation"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
} else {
    Write-Host "Git: no staged changes; recovery content was already committed."
}

Write-Host ""
Write-Host "=== STUDIO-006 FOUNDATION RECOVERED ==="
Write-Host "Backlog update: PASS"
Write-Host "Agent Skills-compatible registry: PASS"
Write-Host "Skill discovery/loading: PASS"
Write-Host "Technology Radar: PASS"
Write-Host "Provider-agnostic audio registry: PASS"
Write-Host "Commercial-license gating: PASS"
Write-Host "Multilingual localization planning: PASS"
Write-Host "Persistent private audio manifest: PASS"
Write-Host "Focused tests: PASS"
Write-Host "Live TTS calls: 0"
Write-Host "Paid provider calls: 0"
Write-Host "API spend: USD 0"
Write-Host ""
Write-Host "STUDIO-006 STATUS: IN PROGRESS"
Write-Host "NEXT: connect and live-verify existing miniverse-kokoro-tts-prod endpoint."
