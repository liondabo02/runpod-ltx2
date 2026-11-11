# AHOS Studio-16 — Text-to-Cartoon pilot

## Owner's objective
Harun writes one story prompt. AHOS should automatically plan, reuse approved characters, animate, voice, lip-sync, render, inspect and deliver a cartoon. The owner should not manually draw each character or discover every missing component.

## What this branch ACTUALLY proves
- A local story input web page and bounded job queue
- Real prompt-to-canonical-cast, action tags, setting and three-scene PLAN generation
- Actual animated MP4 technical preview using pre-existing articulated Aden/Kaan vector puppet routines
- Reproducible CLI, SHA-256, ffprobe metadata, job/result/QA files
- Fail-closed behavior for characters without a rig or missing named characters
- No paid API calls

It DOES NOT prove:
- professional 3D, mesh, rig, approved face identity
- production-grade expressions, voices or lip-sync
- actual 8-minute completed episode or production-ready video
- animation support for all 16 characters
All outputs must keep PRODUCTION_READY=false until genuine evidence exists.

## How to run on Kahta PC
Double-click the repo root Windows launcher named Open-AHOS-Studio.cmd.

Or run this from the repo:
python tools/ahos_studio_ui.py --port 8767

Then open:
http://127.0.0.1:8767/

Alternatively:
python tools/ahos_text_to_cartoon.py --prompt "Aden ve Kaan parkta yuruyor. Kaan emekliyor." --duration 4

Output is under deliverables/AHOS-TEXT-TO-CARTOON/<job-uuid>/ for the UI.
The files are story-plan.json, technical-preview.mp4 (if supported), technical-qa.json, job.json and result.json.

## Technical and safety constraints
- Localhost only (127.0.0.1), no public network listener
- No automatic paid GPU/APIs
- Strict case-insensitive names drawn from the 16-character canonical roster
- A name with no existing visual rig produces a BLOCKED result instead of a fake 3D cartoon
- Limits: 1-2000 text characters, 3-20 sec technical preview, max three queued/running jobs
- No changes to the accepted poster or identity lock
- Not permitted for commercial final release: visual faces are 2D technical approximations
- The final professional QA gate still fails, correctly

## Actual remaining pipeline work
1. Rights-cleared full-body individual character designs, consistent expressions and model sheets
2. Reusable layered 2D or actual 3D rigs that retain owner-accepted identity
3. Real environment and story-dependent camera/prop/character animation
4. Commercially licensed natural Turkish character voices, phoneme timing, viseme lip-sync
5. Multi-scene sound, video composition, QC, repair and final episode output
6. Fill evidence registry and professional gate only when each asset really exists

Existing Ollama models are installed locally but are not integrated into this release; a large-model generation test returned HTTP 500. Do not describe local AI models as already running the studio.
