# AHOS — Independent, as-needed owned-cloud model policy

Owner goal: keep AHOS control-plane, evidence, QA, approvals and worker
orchestration local; use the existing Oracle VM for inference **only when
a bounded model task actually runs**; avoid paid API calls by default.

### What already works

- Existing Oracle SSH forwarding provides local `127.0.0.1:11500` to
  private Ollama `127.0.0.1:11434` on the VM.
- A real `qwen2.5-coder:3b` inference was confirmed. The 7B model is
  considerably slower on 2 OCPU; avoid making it the default.
- AHOS bounded scheduler sleeps/does not call models when idle.
- AHOS TaskBoard/QA/owner approval stay authoritative.

### Safe owner-controlled switch

```powershell
cd C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
python ops\oracle\independent_mode.py --env ahos_core\runtime\model.env
python ops\oracle\independent_mode.py --env ahos_core\runtime\model.env --apply
```

The apply command **fails closed** unless Ollama tags confirm 3B. It backs
up the exact old `model.env` privately under `~/.ahos-private/backups/`
(outside any Git repo), then atomically switches **next daemon launch** to:

- model: `qwen2.5-coder:3b`
- endpoint: `http://127.0.0.1:11500/v1` (loopback only)
- `AHOS_LLM_FREE=1`, `AHOS_ALLOW_PAID_LLM=0`, `AHOS_LLM_MAX_USD=0`
- 180-second timeout; 512 maximum output tokens per request
- inherited kill switch, task limits, QA/approval/risk settings untouched

The active Python daemon **does not hot reload** this change. For rollout,
wait until no mission is running and use the existing supervised daemon
stop/start procedure; verify fresh daemon heartbeat after restart. Do not
run a second daemon against the same runtime directory. If the model
cannot meet the task quality threshold or VM is unavailable, it must be
reported as blocked/pending review, not falsely marked successful.

To roll back the config, use the exact backup path reported during apply:

```powershell
python ops\oracle\independent_mode.py --env ahos_core\runtime\model.env --restore '<backup path>'
```

Restart only at a safe idle point; restoring the env file alone will not
change already running daemon processes.

### Boundaries

- Qwen 3B can be used for small bounded code tasks but is not a substitute
  for a top-tier coding model. Existing CI/browser QA and owner approval
  gates must still reject bad outputs.
- Codex Desktop and DeepSeek Harness are **independent applications**,
  not automatically running inside the Oracle VM just because Ollama is up.
- The current SSH startup uses `StrictHostKeyChecking=no`. A hardened,
  independently verified host key must replace it for stronger security;
  do not assume the current tunnel is protected against host impersonation.
- PC-off execution requires cloud worker/timer health checks and a
  cross-machine durable queue. Local TaskBoard file locks do not cover
  independent hosts.
- "Free" is only the absence of per-token API charges for an already-owned
  model. Oracle compute, storage and networking could have separate charges
  if the tenancy is not within the applicable Free Tier limits.
