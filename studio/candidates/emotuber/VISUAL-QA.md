# AHOS Studio-16 — Emotuber visual QA (2026-11-08)

**Production status: REJECTED / CANDIDATE ONLY.**

This experiment imported the 16 pre-approved roster *poster crops* into Emotuber and ran the site's **free local "Remove BG (AI)"** operation on each. It generated 16 real RGBA PNG derivatives, verified by file checksums and Pillow alpha checks. None is a true editable 3D mesh or layered puppet. No new facial expressions, turnaround angles, or animation rigs were generated. No paid credits used.

## Visual inspection

- **01 Aden:** Recognisable, cutout exists; low-resolution 223×225 crop. Not a full character asset.
- **02 Kaan:** Recognisable; lettering/background residue near bottom.
- **03 Esra, 04 Ahmet, 05 Esma, 06 Harun, 07 Veysel, 08 Öznur:** Nameplates/parts of poster layout remain; not clean transparent character sprites.
- **09 Salih:** Bottom nameplate remains.
- **10 Medine — FAILED:** Cutout segmentation severely damaged the baby image; nearly all pixels at less than full opacity. Not usable.
- **11 Davut — FAILED QA:** Large portions of background/frame remain (only about 18% of pixels have alpha below 250).
- **12 Fatoş, 13 Emoş, 14 Berzan, 15 Aras:** Poster nameplates and/or decorative frames remain.
- **16 Ramin — FAILED:** Almost completely erased (99.92% fully transparent).

**All files are small:** approx. 223–349 px wide. For that reason, even a clean cutout is insufficient for a professional 1080p cartoon as-is.

## Provenance and rights

- Source: existing user-approved roster poster crops under `studio/reference/owner_accepted_roster_v1/characters/`.
- Emotuber's terms permit commercial use only to the extent users hold rights to original inputs.
- The source poster's commercial provenance has not been verified; these candidates must not be automatically approved for monetized production.
- FLUX.1-Kontext-Dev P10 expression sheets have separate noncommercial restrictions; they were **not** used for this export.

## Site tests

- Emotuber: 16 imported, 16 background-removal derivatives saved and extracted.
- Character Bible: free no-login reference-set attempt produced error labels `Forbidden`; no usable new model sheet was exported.
- CharacterKit: free tier allows only 1 character and 10 expressions; full 16-character production was not performed there.

## Integration gate

Do **not** add these PNGs to `studio/production/verified-assets.json` as approved character assets.

Next real production input: individual high-quality, full-body, commercially usable references for each canonical character, then actual model/expression sheets, layered rigs, voices and animation. Keep all original accepted roster assets unchanged.
