# Cartoon Factory

Automated 2D cartoon episode pipeline for a fixed cast of 10 recurring characters.

## Current production foundation

- 10 persistent characters across the full series
- locked series bible, visual style and character-consistency rules
- OpenAI-compatible story/scene planner (`openrouter/free` by default)
- production-ready scene and worker job manifests
- Piper TTS + Rhubarb lip-sync
- reusable character asset contract: reference views, emotions, actions and mouth shapes
- character prompt pack + automatic asset-job builder
- FFmpeg sprite renderer + final episode assembler
- music/SFX worker contract
- FastAPI endpoint for n8n/webhook orchestration
- optional RunPod/LTX-2 path for GPU-heavy special shots
- asset quality gate before episode rendering
- 35-second pilot visual test manifest

## Quality strategy

Normal dialogue/action shots use reusable 2D character assets instead of regenerating the cast every time. This keeps faces, clothes, colors and proportions stable across hundreds of episodes. AI video generation is reserved for shots where it adds real value.

The production gate requires a complete approved character pack before full episodes are rendered. The first target is a polished 30-60 second pilot; only after visual quality is approved should the system scale to 8-minute episodes.

See:
- `config/series.yaml`
- `config/assets.yaml`
- `config/character_prompts.yaml`
- `config/test_scene.yaml`
- `orchestrator/main.py`
- `tools/build_character_jobs.py`
- `tools/qc_assets.py`
