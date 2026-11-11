# AHOS P12-A — Independent technical and creative QA
Date: 2026-11-11. Base commit: 50be4df. Reviewer: ChatGPT.

## Verified evidence
- Actual video: studio/jobs/p12-render/render-technical-5s.mp4
- SHA-256: d287e6588be4130cda7465db435059ab51264e92d38845aec6e9d7ef23c8b4d4.
- File bytes: 228414. FFprobe: 1920x1080, 24 fps, 5.000 seconds, H.264 plus AAC.
- Dispatcher stage: render, VERIFIED_TECHNICAL, production_ready=false.
- Visually inspected actual middle video frame: flat 2D garden, trees, moving kite, debugging words. NO Aden/Kaan or other character.
- Fresh independent targeted tests: 24 passed, exit 0. identity_lock.py --verify exit 0. Professional gate exit 2, FAIL (rightly so).

## Critical defects and boundaries
1. render_backend.py accepts --plan but does NOT read its content. All prompts currently receive the same hardcoded five-second garden and kite. Dynamic story -> film has not been implemented.
2. Audio is artificial pink noise plus a sine tone; it is not a character voice, dialogue or lip-sync.
3. The film contains NO character model, animation or approved identity. The only production-backends.json registration is render; character_model, rig, animation, voice, lipsync, scene and qa are missing.
4. Code sets commercial_license_verified=True as a constant. This is not per-asset provenance evidence. The programmatically generated demo may not use third-party assets, but this does not clear future character posters, candidate art, model weights, sounds, or music.
5. Professional readiness must remain FALSE. Encoder and transport are tested; studio is not producing a professional cartoon.

## P12-B implementation acceptance contract
Primary objective: add a REAL character_model backend for owner-approved Aden that generates genuinely editable 3D character geometry, not another static poster or single textured quad. It must plug into the existing dispatcher and leave all existing branches unmodified.

Implementation:
- Check available local free 3D tools, CPU/GPU, RAM/disk and commercial licenses before install or download. Blender was NOT found on PATH in the recent scan, and the laptop reports approximately 16 GB RAM.
- Reuse approved immutable roster: studio/reference/owner_accepted_roster_v1/characters/01_aden.png and its canon. Do not use FLUX.1-Kontext-Dev noncommercial art as commercial-ready input. Preserve owner accepted references and SHA.
- Develop tools/studio_backends/character_model_backend.py with dispatcher-compatible --plan, --job-dir, --evidence arguments. The backend must READ the plan and the correct character ID, emit an actual BLEND or GLB with real head/body/limbs/hair/clothes/face geometry and reusable scene assets, provide a provenance/rights manifest with SHA-256 and QC.
- Do not claim that a cube, billboard, a raster PNG wrapped on a plane, an empty file, or a similar-looking unrelated face is an approved Aden model.
- If licensing or identity cannot be established, separate TECHNICAL_MODEL_CREATED from OWNER_IDENTITY_APPROVED; keep production_ready=false and put blockers into the job ledger.
- Produce inspectable consistent front, back, profile and three-quarter previews; visually check hair, one yellow star clip, three left cheek freckles, blue kite T-shirt, navy shorts, and shoe color canon. 3yo child proportions.
- Include actual mesh/object/material stats and proof files, tests with tmp_path, missing dependency/invalid input failure cases, exit codes, reproducibility commands, and dispatcher integration.
- Begin the separate rig stage only after a real mesh exists; demonstrate actual joint and face deformation, blinking/waving/walking and store reusable rig for future stories.
- Never mark rig, voice, lipsync, scene, render, or full cartoon complete based on creating a single isolated model.
- Keep all free/zero-new-EUR constraints, no paid GPU/API and no force push or main merges.
- Avoid empty 'agent' directories, README-only deliverables or fake pass statuses.

## Next system-level criterion
The actual owner prompt should produce a different plan and output for different stories. Later the renderer MUST consume actual character, animation, voice, and scene outputs from the pipeline. The current hardcoded 5sec preset is only technical smoke-test evidence.

## Final QA decision
P12-A: VERIFIED_TECHNICAL (render transport proof only).
P12-B: NOT_STARTED / character_model missing.
PRODUCTION_READY: FALSE.
