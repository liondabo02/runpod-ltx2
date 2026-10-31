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
