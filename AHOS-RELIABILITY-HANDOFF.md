# AHOS RELIABILITY — DeepSeek / GPT isolated cooperation

Status: 2026-10-31. This document is a work contract, **not** proof that DeepSeek has accepted or executed it.

## Ownership and collision rules
- GPT isolated branch: `fix/ahos-reliability-20261031`, worktree `C:\\actions-runner\\_work\\AHOS-RELIABILITY-20261031`.
- GPT owns only `ahos_core/ahos/backup.py` and `ahos_core/tests/test_backup.py` in this increment.
- DeepSeek Harness processes are running. Do NOT modify their working directory, uncommitted files, services, locks, queues or providers while they own them.
- DeepSeek can work on the provider reliability / mission execution area ONLY from its separately owned worktree, with an explicit lease and no overlapping file edits.
- No paid model calls without owner's explicit authorization; do not inspect or disclose credentials.
- Never auto-merge a PR into production; owner reviews gate/rollback.

## Read-only findings (not live acceptance evidence)
1. Runtime quality report: delivery 6.5% on a 200-mission sample, `model_unavailable` repeated >40 times.
2. 2026-10-31 runtime: approx. 47-48 blocked missions; provider/timeout and QA form large shares.
3. Daemon and /models endpoints may return alive while real model-produced work still fails.
4. 188 local modified/untracked paths; isolated branch mandatory.
5. Full live suite previously 1009 passed / 5 failed; a separate isolated snapshot of the 4 affected test files yielded 49 passed. Failure is not yet shown to be deterministic.
6. Backups previously omitted worker metrics/audit/taskboard and read SQLite DB main file without WAL snapshot.

## GPT delivered changes
- SQLite online backup into portable temporary database, including committed WAL data.
- SHA-256 manifest and verified ZIP, collision-free archive naming and no known secret file copies.
- Added missing task/worker/CEO records to backup selection.
- Verification: `python -B -m pytest -q tests/test_backup.py` -> 6 passed.
- Full isolated suite pending or run separately; snapshot may include live uncommitted files for testing but only the two backup files are owned for commits.

## DeepSeek task: provider reliability (not yet delegated automatically)
- Locate the real provider chain and model executor before edits; never assume API support.
- Distinguish `/models HTTP 200` from verified `/chat/completions` inference and useful structured output.
- Add a free, bounded, small-token inference preflight (where authorized) with distinct reasons: timeout, unavailable model, rate limit, malformed output.
- Cooldown/circuit breaker after repeat failures; avoid 44× retries of same unavailable endpoint.
- Use local/cloud free sources first, stop with an honest blocker if none works; *no silent paid fallback*.
- Add deterministic mocked tests and one real owner-authorized end-to-end task. Mark `completed` only with real changed files and independent acceptance evidence.
- Report exact tests, model route, cost and residual problems; do not claim 100% availability.

## DeepSeek task: CEO and QA integration (separate owned files)
- CEO -> manager -> worker -> QA -> owner trace with single mission ID and proof.
- Show real per-worker state, not a department-wide synthetic "working" indicator.
- Reconcile missing/blocked/error states with independent acceptance and owner approval.
- Verify replay/recovery after restart, no duplicate dispatch or inappropriate retries.

## Acceptance gates (must pass before any integration)
1. `python -B -m pytest -q` on clean isolated branch, no failures.
2. Free-model production smoke has real output or explicit `unavailable` blocker.
3. SQLite WAL restore, backup integrity and no-secret backup tests pass.
4. Scenario: task -> code diff -> test stdout -> independent QA -> owner decision.
5. No edits to active worktrees; no service interruptions, no deployment and no paid usage.

## 2026-10-31 release gate result — NOT READY

Implemented ahos_core/ahos/release_gate.py as a read-only necessary-check gate (never deploys).
Verification: python -B -m pytest -q tests/test_backup.py tests/test_release_gate.py
Result: 12 passed in 5.81s.

Live runtime preflight results:
- heartbeat: PASS, 22 seconds old
- delivery quality: FAIL, 0.065 over 200 missions, minimum required 0.90
- real delivery evidence: FAIL, missing proof of changed files
- mission queue: FAIL, 65 blocked and 200 completed
- verified backup: FAIL, latest live backup lacks v2 manifest
- clean source: FAIL, 282 paths not committed
- trusted test receipt: FAIL, missing

DeepSeek/operator prioritized independent tasks:
1. Fix model execution to deliver one REAL code change with independent acceptance test, not just /models HTTP 200.
2. Classify blocked tasks, then measure new representative delivery quality; never rewrite historic statuses to game the metric.
3. Coordinate owners of 282 uncommitted paths; never reset their work.
4. Stage WAL-aware backups and prove restore of live-like data.
5. Generate trusted test evidence tied to the exact candidate commit; never fabricate CI provenance.
6. Only after all gates and owner approval, consider reversible versioned production rollout.

## 2026-10-31 — Inference-based routing verification (separate worktree)

New isolated modules:
- ahos_core/ahos/provider_preflight.py
- ahos_core/tests/test_provider_preflight.py

Command (free, only numeric loopback endpoints):
python -B -m ahos.provider_preflight --base-url http://127.0.0.1:11500/v1 --model qwen2.5-coder:7b --fallback-base-url http://127.0.0.1:11434/v1 --fallback-model qwen2.5-coder:1.5b --timeout 10

Actual result:
- tunnel model 7b: unavailable / timeout; previously /models returned HTTP 200
- local 1.5b: real chat completion returned non-empty content (HTTP 200)
- selected local qwen2.5-coder:1.5b, with explicit attempt audit
- tests: python -B -m pytest -q tests/test_backup.py tests/test_release_gate.py tests/test_provider_preflight.py => 22 passed
- THIS SELECTION IS NOT YET ATTACHED TO THE LIVE WORKER EXECUTOR.
- DeepSeek should not treat /models=200 as proof of inference readiness.
- IMPORTANT: No paid model access, real changes to live queue, or deployment.

### Optional live router wiring (not enabled in production)
- ahos_core/ahos/providers.py routes through a real tiny local inference check when AHOS_PROVIDER_INFERENCE_CHECK=1.
- On tunnel failure it can choose local Ollama 1.5b after verified generation.
- If all candidates fail, stale model environment variables are cleared rather than reporting false health.
- Default routing behaviour stays unchanged unless flag is opted in.
- Deterministic provider and preflight tests: 30 passed.
- Activation requires reconciling uncommitted production providers.py ownership and passing full release acceptance; not live now.

### Live acceptance corrections and end-to-end smoke
- In real queue history, 47 missions were cancelled at the same minute; cancelled is NOT a completed deliverable.
- New release gate uses the latest 100 missions via SQLite julianday(updated_at), accounting for mixed timestamp formats.
- Live latest-100 sample: 0 completed, 1 blocked/failed, 47 cancelled, 52 pending. Gate returns NOT READY.
- The 2026-10-31 live affected regression groups returned: 49 passed.
- Local model actual AHOS code-worker run in isolated scratch: www/game.js const a=1 -> const a=2;.
- Isolated acceptance evidence: smoke-sandbox/artifacts/SMOKE-CODE-1_produce/ACCEPTANCE.json passed=true, CHANGES.diff and VERIFY.log.
- Independent direct verification: python -B -c [assert game.js == const a=2;] -> ACCEPTANCE_OK.
- Note: a Windows cp1252 terminal exception affected the smoke wrapper's final printed JSON, not the changed file or acceptance output.
- Four focused test files now return 32 passed.
- Live deployment still disallowed until quality, queue, backup, code ownership and trusted test gates pass.
