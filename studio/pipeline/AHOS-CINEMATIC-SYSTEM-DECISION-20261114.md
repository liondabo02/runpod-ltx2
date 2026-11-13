# AHOS Studio OS — Production quality architecture decision
Date: 2026-11-14
Decision: APPROVE architecture for gated implementation; DO NOT mark production READY.

## Owner product contract

One arbitrary premise from Harun must become a complete script, child-appropriate narrative, storyboard, cast/prop/set manifest, locked reusable models and voices, performance animation, dubbed and lip-synced dialogue, lighting/camera/scene renders, shot repair, edited full episode, independently inspected 1080p24 outputs and one final owner approval. All new episodes in the series reuse identical identity/voice/rig asset hashes.

The owner must not personally design character models or instruct each worker. Autonomous generation of missing reusable assets is the responsibility of AHOS, while licenses, identity acceptance and final release remain explicit gates.

## Independent evidence reviewed

- The attached original 7-second 1280x720/24fps Aden-Kaan motion previews are silent. Visually, the characters are poster silhouette cut-outs without skeletal body deformation. The supplied 2026-11-08 motion report explicitly describes them as 2D silhouette movement, not 3D rig animation.
- The repository's workflows/ltx2_text2video.json contains a generic SaveImage node. The 2026-11-05 repository acceptance report states ComfyUI was not running and no real LTX-2 render took place.
- P12-A verifies video transport/encoding but its five-second garden-kite video does not consume story direction or approved actors.
- P12-B contains an editable technical Blender mesh, not approved Aden identity, UV/rig/acting. The two stages are useful tooling evidence, not production-grade film.
- Studio OS currently compiles persistent story/department tasks; it does not execute all media workers or produce a full episode. Existing remote Oracle draft writer is a draft-only LLM path. The RunPod API previously returned 401/403 and needs real account entitlement checks.

## Decisive choice: rig-driven + AI-refined hybrid

Pure prompt-to-video for every scene is REJECTED for serialized film production. It cannot reliably guarantee immutable faces, clothes, timing, poses and voices across hundreds of separate generations. One pretty clip is a weak benchmark.

Tier 1: LOCKED / DETERMINISTIC actor pipeline
- Original source-approved models/rigs/visemes/voice identities stored in a checksum-based series bible.
- Blender produces deterministic body/face acting, exact object interactions, blocking, camera, light, scene and per-shot anchor frames, depth and pose tracks.
- Generic/unknown characters trigger a new reusable asset work order and independent visual/rights QA before production. Do not require the owner to manually draw every model.

Tier 2: SCENE-CONDITIONAL generative enhancement
- LTX-2.5 Distilled for cheap canary previsualization; IC-LoRA Ingredients, motion/depth/pose controls and DFR for quality/high-fidelity shot refinement. Its native multishot is useful within clips, not a lifetime guarantee for character identity.
- Wan2.2 Animate-14B when reference-guided acting/motion transfer objectively beats the deterministic source on a specific shot.
- The same approved identity/wardrobe/source frame SHA goes to every candidate engine. A video model failing actor identity gets rejected even if overall aesthetics look excellent.
- Keep original voiced dialogue tracks as masters; use generated ambient sound only with verified rights and controllable duration. Lip-sync must be audited independently.

Tier 3: Independent QA + targeted repair
- Technical ffprobe: real audio/video stream, fps, duration, codec, frame integrity, sound stream for dialogue.
- Immutable identity verification: same series character model, rig, voice and source frame IDs across shots and episodes.
- Creative multimodal evidence: at least separate reviewer for identity, acting, motion, prop continuity, cinematography, narrative adherence, Turkish/German audio, children's safety, commercial rights.
- Fail individual categories independently; NEVER average away a face mutation.
- Maximum two automated repair attempts per failed shot, then BLOCKED_NEEDS_CREATIVE_REVIEW rather than silently claiming Hollywood readiness.
- Production output never becomes approved just because the codec/test passes. Every provider must have independent working/render/licensing evidence.

## Skills and agent governance

Skills are capabilities with genuine executors and tests; don't create more named agents just to inflate headcount. The studio needs a director, producer/scheduler, asset vault/identity guardian, acting engine selector, audio director, visual QA critic and compliance reviewer. A job can call existing Blender, Wan Animate, LTX2.5 and voices; the engine must never execute random Internet skills without security/license approval.

## Existing infrastructure and licensing

- Oracle ARM VM: suitable as an always-on Studio OS scheduler/director and artifacts/worker registry after actual server deployment; do NOT run heavy LTX-2.5 inference on it.
- Existing purchased GPU or RunPod: only after active resource availability/credits, tariffs, GPU VRAM and permission are verified. No new expenditure without owner approval.
- GitHub: versioned code, dependency manifests and small evidence; large videos/models in checksum-addressed artifact storage.
- LTX-2.5 model weights: LTX-2.x Community License (free commercial use for eligible businesses under USD 10m annual revenue, conditional on binding terms). Code license differs. Do not silently treat every source image as commercially cleared.
- Wan2.2: official Apache-2.0 distribution. Validate all referenced checkpoints and third-party source assets.
- Tencent HunyuanVideo-1.5: its model LICENSE excludes the EU; exclude from commercial production in Germany.

## Milestones and objective acceptance

S1 CENTRALIZATION: Oracle-hosted authenticated Studio OS API, transactional queue and worker leases, restart recovery; PC off, same job continues.
S2 DIRECTOR: A brand-new owner idea yields full timed screenplay, approved educational objectives, shot-by-shot camera/acting/voice plan, critic revisions, no manual authoring.
S3 IDENTITY ENGINE: A 10-shot episode uses immutable approved cast and voices, auto-builds any missing guest assets, visibly matching references in close-ups.
S4 REAL VIDEO CANDIDATES: Same story shot from approved reference run through Blender, Wan Animate, LTX2.5 in authorized GPU environment. Record hashes, motion/identity outcomes, actual cost/capacity.
S5 AUTO-REPAIR: Failed shots are independently diagnosed and regenerated with locked references, up to two tries and bounded cost; completed shots/assets not regenerated.
S6 REPEATABILITY: Two different full 8-minute TR/DE episodes with coherent child-safe story, genuine mouth/voice sync, locked actors, quality proof; run again on different day and with owner PC off.

**Today's deliverable:** studio_cinematic_router.py + registry + 20 passing GitHub-hosted tests. This is safety policy and decision plumbing, not successful GPU render, voice, rig or completed Hollywood-level episode.

Source links:
https://github.com/Lightricks/LTX-2
https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/README.md
https://github.com/Wan-Video/Wan2.2
https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE

## New image-to-3D and auto-rig technology assessment (14 November 2026)

**Microsoft TRELLIS.2 — CONDITIONALLY SHORTLISTED**. Official image-to-3D 4B model exports high-detail meshes/PBR texture material, potentially far superior as an asset-factory candidate to AHOS's hand-coded Blender sphere geometry. The upstream repo states model/code are MIT, but nvdiffrast/nvdiffrec and third-party preprocessing have their own terms; verify complete dependency graph and the rights of the input poster before commercial operation. Output is an *asset candidate*, not already rigged/visually accepted series identity. https://github.com/microsoft/TRELLIS.2

**AniGen (SIGGRAPH 2026) — RESEARCH-ONLY UNTIL RIGHTS VERIFIED**. An attractive image->mesh+skeleton+skinning candidate for automated actor rigs, but the official project explicitly says bundled extensions/CUBVH are derived from noncommercial/research-only code. Do not deploy the unmodified distribution for a commercial cartoon without resolving those dependency rights. https://github.com/VAST-AI-Research/AniGen

**Wan2.2 Animate-14B — CONDITIONAL MOTION PROVIDER**. The official Apache-2.0 Wan2.2 implementation can drive a reference actor using a source-motion video. It must be tested for the exact stylized face, acting and costume continuity; identity passing is not implied by model support. https://github.com/Wan-Video/Wan2.2

**Voice and lip sync**. Piper has a Turkish tr_TR voice in its official list, but voice naturalness, commercial rights of that specific voice, child-role timbre and 2–5-year-old suitability must be independently evaluated; it is not production-approved. Final dubbing must preserve approved per-character voices and phoneme/viseme timing. https://github.com/rhasspy/piper

**Automatic asset-factory target:** snapshot owner-approved face+wardrobe -> legally clear multiview generation -> image-to-3D candidate mesh and PBR materials -> deformation-friendly topology/retopology -> verified rig/skinning and facial controls -> same-identity multiview QA -> immutable approved GLB/BLEND + rig/voice hash -> reused by Studio OS in every episode. Missing components must generate jobs automatically. The first verified system-wide acceptance is *any* two recurring cast members in multiple distinct scenes with the same genuine reusable assets; do not accept poster crops/spheres as production rigs.

No model downloads, unknown dependencies, paid GPUs, accounts or additional resource rentals were started as part of this research.
