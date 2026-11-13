# AHOS Studio OS — LTX-2.5 conditional adoption and quality gates

**Decision:** Use LTX-2.5 as an optional high-fidelity **shot-generation worker**, not as a replacement for the series bible, identity-locked characters, acting controls, sound mastering or creative QA.

## Official sources
- https://github.com/Lightricks/LTX-2
- https://huggingface.co/Lightricks/LTX-2.5
- https://docs.ltx.io/open-source-model/getting-started/quick-start
- https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/README.md
- https://ltx.io/model/license

**Facts:** LTX-2.5 was released August 11, 2026. It is an open-weights locally runnable model, not a limitless cloud subscription. Local model files in the documented quick start total around 66 GiB. The LTX-2.x Community License permits commercial production in eligible businesses below US$10M consolidated annual revenue, subject to the actual terms; API Fast/Pro are separately billed.

## Why our current output remained poor
- The AHOS legacy workflow file workflows/ltx2_text2video.json is a generic still-image CheckpointLoader / SaveImage demonstration, **not** a real LTX video/audio pipeline.
- The repository's 2026-11-05 LTX2 acceptance report says the render was mocked and ComfyUI was offline during testing.
- The P12-A five-second preset scene does not read real story direction; P12-B Blender Aden mesh is a technical identity-unapproved prototype.
- Better weights cannot rescue an identity-unstable screenplay-to-render architecture. Keep the same approved model and voice across hundreds of independent shots.

## Official LTX-2.5 workflow selection
- Fast canary: LTX-2.5_T2V_I2V_Single_Stage_Distilled.json
- Higher-detail candidate: LTX-2.5_T2V_I2V_Two_Stage_Distilled.json or native DFR pipeline
- Approved cast, wardrobe and set ingredient sheet: LTX-2.5_ICLoRA_Ingredients_Single_Stage_Distilled.json
- Directed actor motion: LTX-2.5_ICLoRA_Motion_Track_Distilled.json and Union Control
- Preserve mastered voice/dubbing timing: LTX-2.5_A2V_Two_Stage_Distilled.json
- Do not mix version-specific 2.3 Dub-It / LoRAs with 2.5 without evidence of compatibility.

## Runnable native worker provided by this branch
tools/ltx25_shot_worker.py implements an explicit, safe, reference-image-conditioned generation command using the official Lightricks Python distilled pipeline. It requires: a SHA-256-locked first frame from the AHOS series bible, reviewed image rights, GPU provider entitlement, installed official model files, uv, ffprobe, and explicit worker authorization. It does not download weights or allocate/bill resources.

The worker produces a real MP4 only when all these prerequisites exist and official inference actually executes. FFprobe verifies a sound video; evidence remains TECHNICAL_CANDIDATE_NOT_APPROVED, with output_identity_approved=false and production_ready=false. **This branch is not a verified GPU run.** The Kahta remote device was offline during this research, and RunPod entitlement/credits have not been confirmed.

### Worker config example (do NOT commit actual credentials)
Use a worker.local.json with these fields: ltx_repo=/srv/LTX-2, model_dir=/srv/models/ltx-2.5, provider=existing-owned-gpu, new_spend_limit_eur=0, license_terms_accepted=true, max_render_seconds=3600. Use JSON values of the proper types.

### Shot plan
Use schema=ahos.studio.ltx25.shot.v1, model=ltx-2.5, license_status=SOURCE_RIGHTS_REVIEWED, shot_prompt=at least 50 characters describing shot motion, lighting, camera, approved actors, reference_frame={path: repo-relative approved image, sha256: actual SHA-256}, frames=121 (5 seconds at 24fps), fps=24, width=1280, height=720, seed=42. No fake placeholder path can pass image hash validation.

### Preflight and execution
- Preflight: python tools/ltx25_shot_worker.py --config worker.local.json --plan path/to/shot.json --job-dir path/to/job --mode preflight
- Render on **already authorized GPU** only: AHOS_EXISTING_GPU_AUTHORIZED=1 python tools/ltx25_shot_worker.py --config worker.local.json --plan path/to/shot.json --job-dir path/to/job --mode render --authorize-existing-gpu
- Do not register as a default production backend until one actual independently reviewed shot runs on existing GPU without spending surprises.

## Objective image/video quality benchmark
With the same approved character frame and storyboard, render two controlled 4–6 second canaries, starting with fast single-stage and then two-stage/DFR (provided budget/capacity is verified). Score: (1) face/costume continuity, (2) smooth natural acting without foot skating, (3) stable background/props, (4) cinematic light/shadow/materials, (5) precise prompt action and narrative, (6) voice/lipsync consistency, (7) real video/audio file integrity. Fail one severe identity mutation. Repair/re-render only the failed shot. Compare with deterministic Blender+rig rendering; use whichever actually passes, not whichever demo looks more impressive.

**Full AHOS success remains the same:** unseen owner story -> script -> locked cast/assets -> coherent shot animation -> TR/DE voices -> QA/repair -> complete 8-minute episode -> owner final approval, repeatable next week with the same identities. This task does not claim that end-to-end goal is completed.