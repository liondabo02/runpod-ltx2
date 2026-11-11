# AHOS STUDIO OS — Autonomous Series Production Architecture

Status: Architecture and tested orchestration prototype; NOT a professional autonomous cartoon studio yet.

## Owner contract
The owner writes one story idea. AHOS generates a complete age-appropriate script, shot list, camera plan, legally usable character/environment assets, acting, voices, lip sync, sound, final rendered film and QA, reusing the same locked faces/voices throughout the entire series. Only final creative approval, additional spending, and irreversible actions require the owner.

Hollywood-quality is a creative acceptance target, never guaranteed merely by resolution, prompt, a script, or tests.

## 1. Required production brain

1. Owner brief and preference profile: standard duration, languages, episode tone and pedagogical goal. The owner should not fill dozens of manual forms.
2. Director and writing room: dramatic treatment, premise, screenplay, dialogue, scene and shot lists, director critique, revised version; all schema-validated and versioned.
3. Series bible: immutable character identities, relations, model/rig/voice hashes, environment/prop registry, visual and narrative continuity, episode chronology.
4. Missing-asset generator: detect missing models, rigs, animations, voices, environments and guest characters, issue automatic jobs, inspect results, approve via creative gate and cache across episodes.
5. Dependency-based production compiler: plan full episode, issue tasks to the correct capable engine, run independent jobs concurrently; pause tasks with missing providers, not the whole program.
6. Capability and skill registry: real executable code/worker, input/output contract, cost, licence, availability, security and QA. Agent names alone are not working agents.
7. Shot-level film workers: resolved 3D/2.5D assets, acting, camera, props, light, language-specific dialogue, phoneme/viseme tracks, render, sound mix.
8. Creative and technical QA: character identity, narrative quality, age suitability, motion, physics, costume, lipsync timing, sound, codecs, legal provenance, time continuity.
9. Self-repair: classify failure, re-run only the failed shot or stage; bounded retry limits, no unlimited queue flooding.
10. Delivery and feedback: finished 8-minute episodes (TR/DE etc), source files, licence dossier, final owner preview and feedback. Never autopublish without approval.

## 2. Physical infrastructure

- Oracle: a LIVE existing Frankfurt ARM VM reached via SSH, with Ollama 3B/7B Qwen models and an active AHOS cloud timer. Target always-on scheduler/director, production DB, project memory and agent coordination.
- RunPod / already purchased GPU providers: target for expensive image, mesh, rig, animation and render work. Current API credentials returned 401/403 during read-only testing, so no GPU work can yet be considered active. No new spending without approval.
- GitHub: code, manifests, asset provenance and system versions; large media should use checksum-addressed artifact/object storage.
- Laptop: optional developer/browser client only. Oracle-hosted service and cloud workers must operate when it is off.
- Budget: No unapproved new charge; existing paid balance only after entitlement, limits and budget controls verified.

The current Studio OS database is local SQLite, not a distributed database. Migrating to an Oracle-hosted transactional task DB is a mandatory step before claiming PC-off autonomy.

## 3. Automated data flow

One owner's text
=> canonical series-bible snapshot
=> original screenplay + creative critic revisions
=> time-coded shots and required production assets
=> per-character/per-scene rights-cleared asset and rig acquisition
=> per-shot animation and language-specific voice/lipsync
=> compositing and sound design
=> shot QA and automatic targeted repairs
=> episode edit and full-length technical/creative QA
=> owner final review
=> delivery, archive and reuse.

The code must re-use an approved character model and rig by their locked hashes. It must NEVER generate another face from scratch in each new shot. New guest characters are automatically given durable IDs and asset-production jobs, but their identity must pass creative QA before final usage.

## 4. Current technical proof (this branch)

- tools/ahos_studio_os.py: persistent SQLite episode registry, event log, typed task DAG, entire 8-minute multi-scene plan, multilingual task expansion, 300-pending cap, owner-source SHA checks, guest asset work-order expansion, and capability discovery.
- tools/studio_os_cloud_writer.py: optional actual text outline draft from existing Oracle Ollama over authenticated SSH. Verified small-scene JSON generation; DRAFT_UNREVIEWED, never promoted to full professional screenplay.
- tools/ahos_studio_ui.py and existing studio/text-to-cartoon/index.html: single button to request a full-episode production job and see real progress/capability gaps.
- tests/test_ahos_studio_os.py: multi-scene DAG, multilingual branching, immutable reference checks, persistence across restarts, queue limits, missing-provider behavior.
- Current professional production readiness: FALSE. No complete 8-minute production film or Hollywood-grade acting pipeline exists yet.

## 5. Missing services that must be built and proven

A. Oracle deployment of authenticated owner API, cross-host safe database, durable job leasing, heartbeat and scheduler.
B. Multi-agent director/writer/critic capable of completing actual timed 8-minute scripts, not only 1-line scene summaries.
C. Generalized rights-cleared asset builder and animator (not Aden-only); series-identity preservation across hundreds of shots.
D. Connected GPU workers and media artifact storage; verified existing entitlements before use.
E. Production Blender/animation/voice/phoneme/lipsync/shot-render adapters. A technical 5-second garden video is not a real render worker for this purpose.
F. Fully automated video and narrative creative QA with bounded correction, final approvals and audit receipts.
G. A true full-episode success test on two novel prompts with Turkish and German final audio and PC-off worker autonomy.

## 6. Final quality acceptance test

Owner enters a NEW story. AHOS produces a complete sound 8-minute 1080p24 cartoon with coherent child-safe narrative, consistent actor identities and voice, a real multi-shot scene sequence, phoneme-aware dialogue, art direction and correct music/lighting. It then produces a different episode with the same immutable cast. It recovers after a worker restart without recreating approved assets. The owner has only final creative approval; real artifact hashes, quality/rights evidence and budget logs are delivered. Any failed professional gate means NOT READY, no matter how many software unit tests pass.

**No more success claims from agent counts, a single .blend, JSON or a fixed demo video.**
