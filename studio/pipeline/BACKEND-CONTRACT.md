# AHOS Studio-16 — REAL backend contract for DeepSeek / Codex / Claude

Do not replace the owner's single story input. This branch adds a production dispatcher to the working text-to-cartoon UI. The user should not manually run dozens of scripts or manufacture a model sheet.

## Verified baseline
- Existing owner interface and technical preview renderer: branch feature/ahos-studio-text-to-cartoon-mvp, commit 67131c7
- Story text -> recognized canonical cast and actions -> 960x540, 12fps **silent articulating vector demo** works
- This production branch adds an adapter dispatcher and owner UI production mode; as of the commit no real 3D / rig / voices are installed and the UI must correctly say BLOCKED
- Original owner-approved roster and identity hashes MUST NOT change
- No paid APIs, force push, noncommercial license laundering or cloud GPU spending

## Your role
Implement genuine commercially licensed, zero-new-EUR local production backends. First prove Aden and Kaan, then scale to the 16-character canon; do not replace them with random lookalike faces. Work on an independent feature branch and do not edit the dispatcher/UI/core files unless the owner agrees.

Stage sequence:
1. character_model: independent reusable full-body 3D mesh/model with preserved identity
2. rig: armature, skinning and face controls
3. animation: actual reusable movement and facial expressions
4. voice: cast-specific natural Turkish dialogue WAV
5. lipsync: phonemes and viseme timings aligned to that WAV
6. scene: camera, environment, props and editable scene
7. render: real full-HD H.264 MP4 with video AND audio
8. qa: mechanical checks and real owner/creative approval

Each stage MUST be a real reviewed script in tools/studio_backends/<stage>.py with CLI:
python tools/studio_backends/<stage>.py --plan ABS_PATH/story-plan.json --job-dir ABS_PATH --evidence ABS_PATH/<stage>-evidence.json

The script creates actual assets INSIDE job-dir, then writes a stage evidence JSON:
{
 "stage":"character_model",
 "status":"PASSED",
 "cost_eur":0,
 "commercial_license_verified":true,
 "cast_ids":["aden","kaan"],
 "provenance":{"source":"local","model_license_url":"VERIFIED_URL","owner_approval_record":"REAL_FILE_PATH"},
 "artifacts":[
   {"kind":"character_model","path":"assets/aden.blend","sha256":"REAL_SHA256"}
 ]
}

Stage to artifact mapping:
- character_model => character_model (.blend or .glb)
- rig => rig (.blend or .glb)
- animation => animation (.blend/.glb/.fbx)
- voice => voice (.wav)
- lipsync => lipsync (.json with a real visemes list)
- scene => scene (.blend/.glb)
- render => film (.mp4, >=1920x1080, at least one audio stream)
- qa => quality_report (.json with technical_pass:true and creative_approved:true, grounded in real owner approval).

Backend registry in studio/pipeline/production-backends.json:
{
 "schema":"ahos.production.adapters.v1",
 "zero_new_euro_spend":true,
 "stages":{
   "character_model":{"script":"tools/studio_backends/character_model.py","cost_eur":0},
   "rig":{"script":"tools/studio_backends/rig.py","cost_eur":0}
 }
}

Safety and verification:
- Scripts must exist under tools/studio_backends and not launch unknown third-party commands.
- Dispatcher validates output paths are inside job folder, SHA256, file extensions and file magic where possible, non-empty artifact size, WAV duration, MP4 video AND audio streams.
- Do not call a PNG with changed extension a 3D model. Do not mark owner approval without actual owner decision.
- Every stage must cover the cast IDs in the job plan; never silently swap in generic stand-ins.
- No fake commercial-license certification. Log the actual model/asset/provider license and provenance, and do not monetize under uncertain rights.
- If a true 3D generator, Blender rig, natural Turkish TTS, or GPU is not available, return a clear BLOCKED error and create an exact remediation item. No premature success.
- Full commercial production still requires the official tools/studio_production_gate.py professional level. Do not weaken it; currently 16 verified character assets + S01E001 video required.

Execution test:
1. pytest tests/test_ahos_studio_dispatcher.py tests/test_ahos_text_to_cartoon.py tests/test_ahos_studio_ui.py
2. POST an owner story to /api/jobs with mode=production
3. Inspect actual assets and hashes, ensure characters look like approved references, verify quality
4. Report real deliverables, failures, costs and Git SHA. No silent fake green statuses.

Owner product: one written story -> persistent characters -> storyboard/script -> character motion -> camera/props -> Turkish voices and real lip-sync -> render -> automatic QA repair -> final 8min S01E001 (later multilingual). All backstage steps should be automated; the owner is only consulted for spending, irreversible actions, new credentials or creative release acceptance. Holding includes other departments, but current work priority is ONLY Studio-16.
