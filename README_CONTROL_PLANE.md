# Miniverse Agent Control Plane

Experimental multi-agent control plane. It is isolated on `feature/agent-control-plane`; production RunPod, models, volumes and the current video workflow are untouched.

## Goal

Run five cooperating AI roles in parallel instead of solving every task serially:

- **supervisor** — decomposes work, assigns roles, synthesizes the final plan.
- **github_scout** — searches repositories/docs/issues/releases and returns evidence, not guesses.
- **builder** — proposes code/workflow changes with rollback notes.
- **qa_sre** — checks schemas, tests, logs, compatibility and regression risk.
- **cost_security** — blocks destructive, paid or security-sensitive actions unless policy allows them.

All agents share a local SQLite ledger so results can be reused by later agents/runs. Model routing is through LiteLLM, so each role can use a different provider/model while the application keeps one interface.

## Safety defaults

`auto_publish=false`, `external_spend=false`, `destructive_actions=false`, max parallel agents `4`. Billing/legal/destructive actions require owner approval. This branch does **not** deploy anything to RunPod.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r control_plane/requirements.txt
cp control_plane/.env.example .env
# fill only the provider keys/models you choose
python -m control_plane.cli "Audit the current LTX-2 I2V workflow and propose the safest next change"
```

## Model routing

Each role reads a model name from an environment variable. Examples can be OpenAI, Anthropic, Gemini, OpenRouter or local endpoints supported by LiteLLM. No key is stored in Git.

## Next integration points

1. GitHub tool adapter: scout read-only, builder branch/PR only, QA status/log read-only.
2. n8n/Redis task queue adapter for persistent jobs.
3. RunPod adapter with an explicit cost gate before any GPU execution.
4. Artifact/QC adapter for generated media.
5. Approval service for spend, publish, billing, legal and destructive operations.

This is the control-plane foundation; it does not replace the existing LTX worker.