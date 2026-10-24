# AHOS Cloud / Codex / DeepSeek — Safe Integration Contract

**Observed 2026-10-24:** Oracle `AHOS-QUALITY-99` VM is RUNNING according to OCI.
Configured size: 2 ARM OCPU / 12 GiB RAM, Frankfurt. This is NOT proof
that Ollama, Qwen, DeepSeek or cloud worker timer is installed/running.

The existing AHOS `runtime/model.env` points to a separate external model
provider and has a nonzero per-run USD limit. Do NOT overwrite it when the
Oracle loopback tunnel is unavailable. AHOS's running Python daemons also
do not hot-reload that env file.

## Safest target structure

- Oracle Ollama binds to `127.0.0.1:11434` on the VM only.
- Local encrypted SSH forwards `127.0.0.1:11500` to that VM loopback service.
- AHOS agents share the local runtime/TaskBoard contract and owner approval.
- Codex is a separate CLI agent authenticated through its own supported login.
- DeepSeek Harness is a separate client/provider; its existing local data
  does not prove it runs on Oracle. An Ollama-hosted `deepseek-r1:7b` is
  an open model tag, NOT the commercial DeepSeek Harness service.
- ChatGPT as a chat subscription is NOT a reusable API credential and does not
  move into the VM. OpenAI API access is separate and may incur charges.

## Verification and staged configuration (NO paid calls)

```powershell
cd C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
python ops\oracle\ahos_cloud_bridge.py --repo .
# After authorized SSH connectivity is functional:
.\ops\oracle\Start-AhosCloudTunnel.ps1 -Model qwen2.5-coder:7b
# If AND ONLY IF deepseek-r1:7b has been installed on the VM:
.\ops\oracle\Start-AhosCloudTunnel.ps1 -Model deepseek-r1:7b
```

The connector creates `ahos_core/runtime/model.cloud.env` **only after**
the requested model tag is returned from the local, SSH-forwarded API.
It never replaces `model.env`, never restarts agents, never spends money,
and never bypasses owner approval. A separate safe maintenance window is
needed to apply the staged file to an idle daemon.

## What remains before claiming complete federation

1. Establish and validate the SSH tunnel and Oracle Ollama /api/tags.
2. Verify the installed model is suitable; **do not** blindly pull another
   7B model or expose port 11434 to the internet.
3. Back up and switch the AHOS model env during an idle window, with explicit
   start parameters and a rollback. Confirm daemon heartbeats show model mode.
4. Test a real zero-cost bounded task; capture produced file, independent QA,
   TaskBoard state, token usage and timeout. Roll back if anything fails.
5. Codex and DeepSeek *external sessions* must each adopt the same task
   ownership API; existing separate CLIs do not automatically share tasks.
6. Oracle cloud worker timer must be verified on the VM before asserting any
   PC-off autonomous work. A local-only TaskBoard is not a distributed lock;
   remote job runners require transactional cross-host coordination.

Never paste SSH keys, API tokens or Codex/ChatGPT login state into shared logs
or the source repository. No new spending was approved by this procedure.
