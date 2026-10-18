# Model routing

The control plane is provider-agnostic. Each role reads exactly one model route from environment variables and LiteLLM translates the request to the configured provider.

## Recommended topology

Use at least three independent model families so one provider/model is not a single point of failure:

- Supervisor: strongest reasoning model available to you.
- GitHub Scout: fast/cheap research-oriented model.
- Builder: strong coding model.
- QA/SRE: a different coding/reasoning family from Builder.
- Cost/Security: inexpensive model or local Ollama model.

LiteLLM currently documents OpenAI, Anthropic, OpenRouter, Ollama, Vertex/Gemini, NVIDIA NIM, Hugging Face, Novita and other providers behind one interface. Exact model names change over time, so production configuration belongs in environment/secrets rather than source code.

## Example routes

These are examples of valid LiteLLM route styles, not hard-coded requirements:

```dotenv
MINIVERSE_MODEL_SUPERVISOR=openai/gpt-5
MINIVERSE_MODEL_SCOUT=openrouter/<provider>/<model>
MINIVERSE_MODEL_BUILDER=anthropic/claude-sonnet-4-5-20250929
MINIVERSE_MODEL_QA=novita/deepseek/deepseek-r1
MINIVERSE_MODEL_COST=ollama/<local-model>
```

Provider credentials must be injected as environment variables/secrets supported by LiteLLM. Never commit API keys to GitHub.

## One-key option

If minimizing setup is more important than provider independence, several roles can initially route through OpenRouter with one OpenRouter key. Later, move critical roles to direct independent providers.

## Free/local option

Ollama requires no external API key and can be used for one or more low-cost roles if a suitable local machine/server is available. Cloud providers may have free quotas, but quotas and eligible models change; do not assume cloud inference is permanently free.

## Verification

Before making any paid model call, run:

```bash
python -m control_plane.preflight
```

This validates that all five routes are configured. It intentionally does not call any model and therefore does not create inference cost.
