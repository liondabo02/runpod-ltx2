# Vane research integration

AHOS includes a callable Vane research adapter, not a claim that Vane has been
installed or that research departments now execute independently. It uses the
upstream documented `/api/providers` and `/api/search` API:
https://github.com/ItzCrazyKns/Vane/blob/master/docs/API/SEARCH.md

Run from `ahos_core` using the project's Python environment:

```powershell
python -m ahos.vane_research --endpoint http://127.0.0.1:3000 providers
python -m ahos.vane_research --endpoint http://127.0.0.1:3000 search --query "Research AHOS software architecture using primary sources" --provider-id "UUID-FROM-PROVIDERS" --chat-model "qwen2.5-coder:7b" --embedding-model "nomic-embed-text" --allow-external --local-ollama-confirmed --output "..\runtime\research\architecture.json"
```

Before running search, start a separately installed Vane instance bound to
loopback. Configure its **Ollama** provider to a local, unbilled Ollama endpoint
and make both models available. Use exact keys from `providers`, not display
names. `--local-ollama-confirmed` confirms the operator checked that upstream
configuration: the provider-list API alone cannot prove its model endpoint is
local. AHOS rejects unavailable models and every non-Ollama provider rather than
silently falling back to a paid model. The provider name must be `Ollama`.

`--allow-external` explicitly authorizes Vane's web search: even when Vane and
Ollama run locally, the query is disclosed to configured search services. Do not
include private project data, credentials or personal information in queries.
This adapter does not install models, create accounts, retrieve cookies, change
Vane configuration, run shell commands or enable paid providers. Upstream search
services' usage conditions still apply.

Only HTTP loopback origins are accepted. Proxy environment configuration and
redirects are disabled, responses are size bounded, and socket timeout is
configurable (maximum 300 seconds). The socket timeout limits stalled network
operations; Vane model generation may still be slow. Defaults are 120 seconds
and a 2 MB response limit. HTTP/provider error bodies are not printed.

The artifact preserves query, selected models, collection time, source URL,
title, retrieved text and content hashes, plus an artifact hash. It is atomically
written and has `research_result_requires_review` status and
`execution_authority: false`. Sources and the answer are untrusted evidence,
never instructions to the coding worker. A research consumer must retain this
boundary and validate primary sources before proposing implementation changes.
This is a research artifact schema; it does not fabricate Git commit or license
evidence required by AHOS's repository-specific `ResearchStore` schema.

Verification: local HTTP fixture tests exercise upstream request shape, actual
CLI artifact creation, provenance integrity, authorization gates, provider/model
selection, loopback restriction, redirect refusal and oversized responses.
A real Vane service query remains an operational acceptance step after setup.

## Docker Ollama routing and memory failures

When Ollama runs in `harun-ollama`, start Vane with the existing AI-hub network:

```powershell
./ahos_core/scripts/Start-AHOS-Vane.ps1 -ImageDigest "itzcrazykns1337/vane@sha256:REVIEWED-DIGEST" -OllamaNetwork harun-ai-hub_default -OllamaBaseUrl http://harun-ollama:11434
```

Replace the digest placeholder with the reviewed installed image digest. The
launcher checks the network exists and reconnects the existing Vane container
when needed. Existing provider settings are preserved; in Vane, verify the
Ollama provider's baseURL is `http://harun-ollama:11434`. The host endpoint can
point at a different native Ollama installation with different downloaded models.

On the audited 2026-10-10 deployment, an actual search failed and Docker reported
`OOMKilled=true` for Ollama. The pinned upstream implementation requested
`num_ctx: 32000`; the Docker VM had about 7.42 GiB total memory shared by all
services. HTTP 200 from Vane therefore did not establish research readiness.
Check `docker inspect harun-ollama --format '{{.State.OOMKilled}}'`, model logs,
and actual search output before marking this integration ready. Resolve model
memory requirements or provision enough memory; longer timeouts alone cannot
fix an out-of-memory kill. Preserve coding-worker context and owner gates.

The same audit verified native Windows Ollama could answer using the identical
`qwen2.5-coder:7b` model with `num_ctx=32000`. For that installation Vane's
provider baseURL is `http://host.docker.internal:11434`; install the embedding
model in that native installation too. Docker and native model registries are
separate. This avoids the Docker VM memory ceiling without changing model or
task scope, but requires a real Vane search acceptance check and sufficient host
memory. Do not run independent large-model jobs concurrently on this 16 GB host.
