# AHOS Model Gateway

The gateway plans model-provider routes without making a network request. It is
fail-closed: external access, paid use, unverified free models, and sensitive
data all require their applicable gates to pass.

## Default provider roles

- OpenRouter: free multi-model routing for public/internal research and coding.
- NVIDIA NIM: multimodal/speech/retrieval evaluation and future self-hosting.
- Bytez: experimental discovery across text, image, audio, and video models.

Only `openrouter/free` and explicit `:free` OpenRouter model IDs are recognized
as free by default. NVIDIA NIM and Bytez catalog entries change over time, so a
model ID must first be placed in that provider's `free_model_ids` allowlist.

## Non-negotiable gates

1. External providers require `allow_external=True`.
2. A positive estimated cost requires `owner_approved_paid=True`.
3. A zero-cost request must use a verified-free model ID.
4. Public gateways reject confidential and restricted data.
5. API credentials are referenced only by environment-variable name and are
   never returned by a route plan or stored in the repository.

The gateway currently prepares routes only. A live HTTP execution adapter must
remain disabled until credentials are supplied outside Git, provider terms are
accepted, and the owner explicitly authorizes live execution.
