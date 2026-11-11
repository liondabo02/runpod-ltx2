# AHOS P12-B independent creative & pipeline QA — 2026-11-11

## Provenance and scope
Base commit `3b52f09`. Examined actual 700x700 front, 3/4, and face-close Blender previews from `studio/assets/character-library/aden/v1/previews/`, code in `tools/studio_backends/{character_model_backend.py,build_aden_blender.py}`, and `model-manifest.json`. Compared visually against the owner-accepted `studio/reference/owner_accepted_roster_v1/characters/01_aden.png`.

## Decision
- **Blender editable 3D technical geometry: VERIFIED.**
- **Approved Aden likeness: FAIL / PENDING_IDENTITY_REVIEW.**
- **Production character ready: NO.**
- **Rig and skinning: MISSING.**
- **Model version reuse: partially implemented.**
- **PRODUCTION_READY: FALSE.**

### Visual findings
1. The model is clearly a different stylized child than the approved Aden. The reference has smooth expressive face proportions, smaller integrated nose, natural smiling mouth, side-parted dark brown wavy hair, and cinematic soft shading. The new model has separated bulging eyeballs, exposed teeth in a cylindrical mouth, ball-like nose, flat/sharp hairline, large globular hair clumps, flat shader and doll-like limbs.
2. Correct broad identifiers are attempted: dark brown hair, one yellow star, blue shirt, dark shorts, three dots on cheek and cream-colored sole. But these *symbolic attributes* do not establish facial identity.
3. Three left-cheek freckles are represented as raised spheres instead of natural flat skin marks.
4. The shirt carries a simple yellow diamond, not a legible kite print.
5. Shoes are blue with cream soles and added yellow dot/star accents. Written canon and approved visual references need a definitive standard; no automatic approval.
6. Model consists primarily of procedural spheres and cylinders. Object count and vertex totals demonstrate editable meshes, but **do not measure likeness or animation suitability**.
7. No articulated skeleton, skinning, facial blend shapes, UV atlas or texture details. Rigging this particular low-likeness face now would turn a visual prototype into a long-lived wrong character.

### Code findings requiring correction
1. `character_model_backend.py` is hard-coded to Aden: `ROSTER`, `BUILD`, `LIBRARY`, `character_from_plan`. Selecting another canonical character does not create that character. This does not yet scale to 16 cast members or arbitrary story scenes.
2. `character_from_plan` finds Aden within a plan even if the plan also contains other characters and produces ONLY Aden. A multi-character story is not fulfilled. Asset requests must enumerate all cast, deduplicate by character ID, and produce a per-character status.
3. Library reuse checks only presence of `.blend` and `model-manifest.json`; **does not check source reference SHA, mesh/GLB hashes, model spec/schema version or required preview integrity before reusing**. Future asset corruption or stale identity could silently propagate.
4. `commercial_license_verified=True` is hard-coded. Blender-generated original geometry may be clear of third-party meshes, but owner poster provenance, potential licensed source materials and derivative rights must be tracked separately. Commercial readiness should only be true for the specific verified source chain, not blanket approval.
5. Backend `validate` requires minimum vertices and preview count but not compatible topology, sensible rigging interfaces, actual identity consistency, source rights or deformable construction.
6. The branch includes backup `.blend1` in the reusable asset library; treat backups as build artifacts and avoid unreviewed growth.

## Next production milestone: P12-C (correct order)
**A. Generalize character asset pipeline** rather than repeating Aden-only build for 15 other characters. Create an ID-driven registry that consumes each owner's approved reference and character-specific immutable canonical attributes. Backend inputs are multi-cast stories; outputs and QA per cast member. Add strong SHA-based asset cache invalidation.

**B. Improve Aden identity before final rig.** Use high-quality rights-cleared reference-controlled art and/or 3D modeling workflow to make a recognizable *same Aden* with continuous hair, more natural face topology, eyelids, lips/teeth, natural freckles, actual kite-print shirt and documented footwear canon. Deliver 6 matched views and side-by-side comparison against original reference. Multiple iterations allowed, but only retain improved models after creative QA. Do not overwrite old version v1.

**C. Prove actual deformation on a separate, explicitly technical rig prototype:** armature + weight painting and independent eyelid/mouth face controls, with 3 short evidence animations (blink, wave, walk). This can proceed in parallel on v1 only if explicitly labeled TECHNICAL_RIG_NOT_APPROVED_CHARACTER, so it is not mistakenly registered as the final Aden.

**D. Integrate source-verified versions into text-to-cartoon:** for an arbitrary story, select correct models, work out missing asset generation, and re-use previous versions without altering identities. Keep studio professional gate failing until all 16 complete production-ready assets + authentic voices / lip-sync / episode render meet approval.

### Test & release contract
- All current tests pass on independent worker environment; source identity lock remains unchanged.
- Tests must include multi-character requests, wrong cast, corrupt/replaced manifest/model, changed source SHA, reuse after valid cache, no Blender, and absence of commercial rights proof.
- One true mesh source and six actual renders per model; model opens and exports to GLB; topology and movement evaluated.
- Never mark a simple procedural primitive as HOLLYWOOD / FINAL / OWNER_APPROVED.
- No new paid GPU or API without owner approval, no force pushes, no main merges.
