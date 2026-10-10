# AHOS free AI integration review — 10 October 2026

This is a reviewed candidate list, not a claim that all candidates are integrated.
The current bottleneck is correct code production and validation, not agent count.
No new accounts, billing, credentials, cloud inference, or model downloads were started in this review.

## Verified local state

- Gemini CLI 0.63.0 is already installed on the Windows host. Its help supports headless JSON output, plan mode, sandbox and worktrees. Authentication and remaining free quota are not verified.
- Native Ollama has qwen2.5-coder:7b and nomic-embed-text. The loaded coder is CPU-only. Docker Ollama is a separate installation; do not assume its models are native models.
- Read-only probe: `python ahos_core/scripts/free_ai_preflight.py`. It queries loopback metadata and prints key-presence booleans only. Installation/key presence never proves successful model execution.

## Candidates and concrete roles

| Candidate | Cost/license distinction | AHOS role and next gate |
| --- | --- | --- |
| Google Gemini CLI | Apache-2.0 CLI. Official quota page: personal Google account 1,000 model requests/day; unpaid API key 250/day, Flash only. These are requests, not completed tasks; service availability applies. | Priority coding reviewer/alternative worker. Use official CLI headless interface in an isolated worktree; keep AHOS scope, tests and owner approval. Verify existing auth and free entitlement before inference. Never extract OAuth tokens for a custom API client. |
| Google ADK | Apache-2.0 framework; model services priced separately. | Evaluate durable department delegation, retries and human review through a separate prototype. Keep existing queue authoritative until an actual compatibility test passes. |
| DeepSeek-R1 | Official repository and weights MIT; distilled Qwen and Llama variants retain underlying license considerations. Hosted DeepSeek API has paid token pricing. | Candidate local independent reasoning reviewer. Benchmark an installed compatible distilled model in isolation before downloading another. Full model is not a practical CPU replacement for this host. Do not assume reasoning quality equals exact-edit coding quality. |
| Microsoft Agent Framework | MIT framework; inference/providers separate. AutoGen is in maintenance mode and directs new projects here. | Alternative to ADK for restartable multi-department workflows. Compare one workflow, not install multiple redundant orchestrators. |
| CrewAI | MIT framework; hosted services and model inference separate. | Department-role workflow experiment. Require artifact evidence and cancellation/retry compatibility before adoption. |
| OpenHands | Current official repository describes Agent Canvas and MIT licensing. | Candidate operator UI for coding agents including Gemini. Verify current component/version and AHOS task bridge; a running UI does not prove shared queues. |
| OpenRouter free entries | Only catalog entries explicitly offering a free variant qualify; availability and quotas vary. | Existing cloud fallback candidate. Check catalog price, account quota, data policy and cooldown; never substitute paid entries automatically. |
| Groq | Model/org-specific free limits; account limits are authoritative. | Fast reviewer or research summarizer candidate. Check actual account tier, data handling and language quality. |
| Hugging Face Inference Providers | Monthly credits are limited; routed inference pricing is separate from open model licenses. | Model discovery/evaluation, not unlimited production inference. |
| NVIDIA NIM / Bytez | Hosted trials/free offers must be confirmed per model/account; local model/runtime license is separate. | Catalog candidates only until entitlement, commercial terms and limits are verified. |

## Google data and audience distinctions

Gemini API terms effective 23 March 2026 provide an EEA/Switzerland/UK data-handling exception: paid-service data rules apply even to unpaid quota there. Do not repeat the blanket claim that every German free-tier prompt trains Google models. These API terms also require paid services when making API clients available to users in those regions. They restrict clients directed at under-18s. Internal adult-operated cartoon production is a different design from a child-facing Gemini chat client; review intended use before deployment.

Gemini CLI Google-account login uses Code Assist terms, not automatically Gemini API-key terms. The official CLI notice prohibits third-party direct access to its underlying service using reused CLI OAuth. Use the official CLI, or an authorized API key with the correct API terms.

## Acceptance before enabling any new worker

1. Full original task preserved; no test weakening or scope expansion.
2. Isolated checkout without runtime credentials or personal files.
3. Real candidate patch, deterministic validation and passing sandbox tests.
4. Separate evidence for quota, billing tier, privacy and commercial license.
5. Bounded retries/cooldown and owner-controlled application/publication.

## Official sources checked

- https://geminicli.com/docs/resources/quota-and-pricing/
- https://geminicli.com/docs/resources/tos-privacy/
- https://geminicli.com/docs/cli/headless/
- https://ai.google.dev/gemini-api/terms
- https://ai.google.dev/gemini-api/docs/pricing
- https://github.com/google/adk-python
- https://github.com/deepseek-ai/DeepSeek-R1
- https://api-docs.deepseek.com/quick_start/pricing/
- https://github.com/microsoft/autogen
- https://github.com/microsoft/agent-framework
- https://github.com/crewAIInc/crewAI
- https://github.com/OpenHands/OpenHands
- https://openrouter.ai/docs/guides/routing/model-variants/free
- https://console.groq.com/docs/rate-limits
- https://huggingface.co/docs/inference-providers/pricing
- https://build.nvidia.com/
- https://docs.bytez.com/model-api/docs/welcome
