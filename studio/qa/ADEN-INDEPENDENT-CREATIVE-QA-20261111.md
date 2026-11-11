# AHOS Studio-16 — Independent Creative QA / Aden (2026-11-11)

## Scope and evidence

A human-vision review of the currently accessible **approved poster crop**
`studio/reference/owner_accepted_roster_v1/characters/01_aden.png`
and the existing **candidate image sheet**
`studio/candidates/aden/model-sheet/ADEN-model-sheet-candidate-v1.png`.

These are the original files in the branch from which this review worktree was created. This review does **not** approve new art, replace the owner's reference, or represent a full 3D production audit.

## Decision: CANDIDATE ONLY — NOT APPROVED FOR PRODUCTION RIG

### Confirmed similarities

- Aden reads as a young girl with dark brown, wavy shoulder-length hair.
- Yellow star clip remains visible on the hair in all views.
- Blue kite-print shirt and dark navy shorts are recognizable.
- Cheerful expression, dark round eyes, warm cinematic CGI look.

### Visual issues actually seen

1. **Wrong shoes:** Candidate views depict predominantly bright BLUE sneakers, some with extra yellow stars. Target canon specifies **cream sneakers with blue soles**. Poster crop also shows blue elements, so use the *approved written clothing canon* as the shoe-color source of truth and request owner review where image/text conflict.
2. **Star size and hair placement:** In some views, especially the standalone right-facing pose, star clip appears exaggerated. A single consistent clip should be preserved with coherent position across camera angles.
3. **Freckle consistency:** Source/brief requires exactly three freckles on Aden's LEFT cheek. The dots in the front, 3/4 and profile views are hard to track or are located inconsistently; this cannot pass an automated identity gate without a per-view check.
4. **View/crop defects:** The supposed left profile has stray hair imagery on its left edge; the face/body is partially cropped in the view frame. It cannot serve as an orthographic modeling blueprint as-is.
5. **Right profile differs in staging and scale:** It shows a small dynamic walking pose rather than the same-neutral-T-pose reference scale used for the others. A full-height orthographic matching right profile is missing.
6. **No uniform modeling coordinate system:** Different pose/scale/projection and shaded backgrounds make technical reconstruction inconsistent. Need aligned head height, foot-ground plane, front/back/side T/A-pose, clear separated panels.
7. **Not rig sources:** All views are flattened raster images, not mesh, editable layers, armature, morph targets or skeleton; they are unsuitable as a replacement for a real character rig.

### Rights

The candidate sheet identifies its model as FLUX.1-Kontext-Dev and references **NON-COMMERCIAL** terms. Verify output rights using official license and provider terms before any commercial use. The underlying approved poster's creation provenance and rights remain unverified. Until documented, all outputs must be labeled `CANDIDATE_NONCOMMERCIAL_UNCLEARED` and never `PRODUCTION_APPROVED`.

## What the next technical/modeling team must deliver

1. Produce or obtain a rights-cleared, source-consistent orthographic Aden turnaround: front, back, left, right, 3/4; neutral stance and matching scale; separate files with documented rights.
2. Obtain the owner's approval on a single identity-locked reference, including star and 3 left-cheek freckles, hair silhouette, clothing.
3. Create one **real** editable character mesh and facial/body rig or fully layered 2D equivalent; if using 2D, label it 2D honestly.
4. Show an independent movement proof: blink, wave and walking over time with **same identity**, plus source files.
5. Then pass independent visual QA for anatomy, face identity, continuity, garment detail, clipping and license. Do not relax existing professional gate.

## Practical pass/fail checklist

| Check | Current candidate | Required |
|---|---|---|
| Name/age appearance | PARTIAL | 3-year-old Aden, consistent |
| Yellow hair clip | PARTIAL | One, stable size and position |
| Three left-cheek freckles | UNVERIFIED | Exactly 3 in every visible view |
| Shoes/costume | FAIL | Written canon and owner-approved reference |
| Five orthographic aligned angles | FAIL | Aligned full-body source art |
| 3D mesh or layered rig | MISSING | Editable, deformable real asset |
| Blink, wave, walk | MISSING | Rendered continuous action |
| Real Turkish voice/lip sync | MISSING | Audio aligned to animated face |
| Commercial provenance | BLOCKED | Source and model licenses verified |
| Professional gate | FAIL | Genuine technical and creative QA |

## Integration guidance

Do not change `studio/reference/owner_accepted_roster_v1/`. This file is a new review artifact, and must not be used as evidence that a complete production model exists.

Existing `feature/ahos-cartoon-production-adapter` dispatch system currently has 21/21 focused tests passing but its `studio/pipeline/production-backends.json` stage map is empty. A production backend delivering actual files—not a new static vector demo—is the next engineering priority.

**PRODUCTION_READY = FALSE**
