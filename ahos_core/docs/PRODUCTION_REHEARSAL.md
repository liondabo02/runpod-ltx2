# Professional episode production rehearsal

`ahos-studio-rehearsal` produces a traceable, local rehearsal of one eight-minute
episode. It connects the canonical character bible, deterministic story planner,
scene/shot/prompt graph, render-job manifest, and seven-language localization
plan without calling a paid provider, a network service, or a publishing target.

The command is intentionally fail-closed. A successful rehearsal is not a
finished cartoon and never reports `release_ready=true`. It records the exact
remaining owner, character-reference, voice-enrollment, localization, render,
and final-QA gates.

## Run from the repository root

```powershell
cd ahos_core
python -m ahos.production_rehearsal `
  --output ..\runtime\studio-rehearsals\S01E001
```

Use a new output directory for every rehearsal. Existing evidence is never
overwritten. The default run leaves the story at `awaiting_owner_story_approval`.

After the owner has reviewed `artifacts/episode.json`, approval can be recorded
explicitly in a new rehearsal:

```powershell
python -m ahos.production_rehearsal `
  --output ..\runtime\studio-rehearsals\S01E001-approved `
  --owner-approve-story
```

This advances the report only to `blocked_pending_external_assets`; it does not
authorize or execute RunPod, TTS, rendering, payment, or publishing.

## Evidence produced

- `rehearsal-report.json`: status, checks, blockers, counts, and evidence hash.
- `artifacts/episode.json`: exact 480-second screenplay packet.
- `artifacts/production-graph.json`: scenes, shots, prompts, references, and provenance.
- `artifacts/render-jobs.json`: deterministic seeds and disabled render jobs.
- `artifacts/localization-plan.json`: every dialogue line across TR, Kurmanji,
  DE, AR, FR, ES, and EN, with human review requirements.
- `state/*.db`: versioned character, story, graph, and render-job state.

The canonical cast contains sixteen locked profiles. Infant and toddler voice
constraints, family relationships, headscarf/pregnancy continuity, twin identity,
and Harun's established organizing role are encoded in the character bible.
