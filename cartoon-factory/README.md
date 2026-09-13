# Cartoon Factory

Dedicated project folder for the autonomous multilingual 2D cartoon system.

## Core concept

- 16 locked recurring family-universe characters
- Harun as the dominant family anchor
- Aden and Kaan as child co-leads
- episode-specific guest characters are allowed without altering the fixed cast
- Telegram-first control: even a single word can be expanded into an ~8 minute episode
- multilingual output in Turkish, German, Arabic, French and Spanish

## Current production foundation

- locked series bible, visual style and character-consistency rules
- OpenAI-compatible story/scene planner
- production-ready scene and worker job manifests
- 5-language localization while preserving scene timing
- Chatterbox Multilingual V3 voice-service path + Piper fallback
- Rhubarb lip-sync cue generation
- reusable character asset contract: reference views, emotions, actions and mouth shapes
- character prompt pack + automatic asset-job builder
- reusable background/world bible
- FFmpeg sprite renderer + per-language final episode assembler
- music/SFX worker contract
- FastAPI endpoints for n8n/webhook orchestration
- Telegram bot gateway
- optional RunPod/LTX-2 path for GPU-heavy special shots
- RunPod character-generation worker package
- asset quality gate before episode rendering
- 35–60 second pilot test target before full 8-minute production

## Quality strategy

Normal dialogue/action shots use reusable 2D character assets instead of regenerating the cast every time. This keeps faces, clothes, colors and proportions stable across hundreds of episodes. AI video generation is reserved for shots where it adds real value.

The production gate requires approved recurring-character packs before full episodes are rendered. The first real target is a polished 35–60 second pilot; only after visual quality is approved should the system scale to 8-minute episodes.

## Project root

This project is intentionally isolated under `cartoon-factory/`. Do not place Cartoon Factory implementation files in the parent LTX2 project root.

See:
- `config/series.yaml`
- `config/assets.yaml`
- `config/character_prompts.yaml`
- `config/backgrounds.yaml`
- `config/languages.yaml`
- `orchestrator/main.py`
- `tools/build_character_jobs.py`
- `runpod/character_worker.py`
- `STATUS.md`
