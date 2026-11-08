# AHOS Completion Integrity — integration and DeepSeek ownership handoff

Date: 2026-11-01. Status: code and tests ready in independent worktree; NOT LIVE DEPLOYED.

## Discovery in production database (read-only)
- At first audit, `completed` column had 600 records: 324 with nested result.status=blocked, 72 without result_json, 204 internally consistent but without independently verified artifact+QA evidence.
- Next production release gate check saw 687 records, 483 inconsistent, highlighting that the bypass remained active.
- Do NOT mass-update historic records to completed, delete errors, or reset queued missions. A data reconciliation plan is required.

## Concrete bypasses located in active, uncommitted code
- `ahos_core/ahos/daemon.py:737` executes direct `UPDATE missions SET status='completed' ...` for documents, including previously blocked jobs, without independent QA and without replacing result_json. The direct update explains the shape of the recorded mismatch; independent attribution of every historic record remains unverified.
- `ahos_core/ahos/queue_drain.py` has a fast path using `apply_simple_edit` to mark a `MissionResult` completed with zero steps. Review before production: no independent QA receipt is created there.
- The owner console already supports `doc_factory` via the normal `_execute` orchestrator, then `_document_qa` or `_unverified_qa`. Prefer this leased route over direct document SQL completion.
- Live DeepSeek Harness and daemon currently work in the main tree; do not change their files without an ownership lease.

## Proposed isolated fix
- `ahos_core/ahos/completion_integrity.py`: read-only, redacted inconsistency audit; default 1000 newest rows, distinguishes unverified narrative from real receipts.
- `ahos_core/ahos/autonomous_company.py`: rejects a blocked result, mismatched task identity or unfinished steps in queue.complete before DB writes.
- `ahos_core/ahos/release_gate.py`: fails closed on contradictory completed records and direct SQL completion bypasses.
- `tools/prepare_doc_hotfix.py` plus `patches/disable_unverified_document_completion.patch`: removes the unsafe direct-document path in a proposed patch against the CURRENT live daemon source, without changing the live file.
- Patch generator tests pass on synthetic input; `git apply --check` against active live worktree did not pass (mixed CRLF / concurrent file edits); reviewer must rebase manually, do not auto-apply.

## Verified test evidence
- `python -B -m pytest -q tests/test_completion_integrity.py tests/test_completion_guard.py tests/test_doc_hotfix_patch.py tests/test_autonomous_company.py tests/test_release_gate.py --tb=short`
- Last result: 33 passed in 16.84 seconds.
- Read-only live SQL scanner detects `daemon.py:737`.

## Required next acceptance steps before production
1. Agree with DeepSeek on ownership of daemon.py, queue_drain.py and owner_console.py; keep live work untouched until handoff.
2. Remove direct SQL shortcut, route docs via leased owner console and genuinely independent QA; ensure no other bypass exists.
3. Make both basic file edits and document outputs produce verifiable hash, test and QA receipts; do not treat worker prose as proof.
4. On isolated clean checkout, run entire test suite and real model->file->QA smoke; test post-restart recovery.
5. Reconcile existing 483 inconsistent historical records as audit exceptions, not as successful deliveries; preserve originals.
6. Create verified restore point and owner-approved reversible rollout, then monitor NEW mission completion samples.

## Isolation
- Worktree: C:\actions-runner\_work\AHOS-COMPLETION-INTEGRITY-20261101
- Branch: fix/ahos-completion-integrity-20261101
- No paid models, live queue mutations, process interruptions, deployment or file deletion performed.
## 2026-11-01 per-turn DeepSeek collision check and lease fix
- Compared the live worktree with this branch BEFORE editing. Live branch remains feature/agent-control-plane (head ecd6dbd); candidate initially clean (head 06c1b62).
- Live had 199 git porcelain entries (290 actual changed/untracked paths). DeepSeek Harness process count 14. Main daemon.py, owner_console.py and autonomous_company.py remain dirty and likely in use.
- New read-only tools/parallel_agent_preflight.py: compares Git merge-base, committed deltas, unstaged and untracked paths; redacts sensitive filenames; returns nonzero if an ownership collision/dirty live tree exists.
- Actual collision preflight found 6 overlapping paths: autonomous_company.py, daemon.py, owner_console.py, providers.py, worker_runtime.py and tests/test_daemon.py. DO NOT cherry-pick/merge these without reviewing live owners' modifications.
- Added failure-safe recording when queue.complete rejects an invalid result. Both CompanyLoop and OwnerConsole now record the mission BLOCKED, release the lease and suppress a fake completion. The error reason records an exception TYPE, not raw task data.
- New tests verify a wrong-mission claimed completion cannot strand a lease in either execution path.
- Legacy queue.complete still accepts a valid, zero-step MissionResult.COMPLETED. This remains an important residual risk: no proof of independent QA/file diff merely from status. Require an explicit verified receipt before enabling a strict production gate.
- Live daemon's direct SQL document bypass remains present and active. The staged patch in this branch is not applied to the live tree and did not pass git apply --check on the mixed-line-ending file; actual owner must review/rebase.
- Current daemon-state last tick was stale despite agent-office HTTP 200. Never equate a responsive UI with a working production queue.
- New scripts and tests are in the separate fix/ahos-completion-integrity-20261101 branch only. No writes to live queue, no deployment, no paid calls.

## 2026-11-01 01:20 Berlin — completion wave and database hardening
- Closing per-turn scan revealed 2,000 rows switched to completed during a single minute, 2026-10-31 23:58 UTC (2026-11-01 00:58 Berlin), with missing result_json. This likely reflects a bulk SQL status transition; the initiating program/agent is NOT established.
- Complete read-only audit then showed 2,687 completed-status rows: 2,072 no result, 386 nested result.status=blocked, 25 no steps, 204 internally consistent but still not independently verified by file/test/QA.
- No retroactive status changes, deletes, or migration on live data. NEVER count the 2,000-row update as real work completion.
- New read-only tools/completion_wave.py reports only aggregate timestamps and counts; no objectives, IDs or error contents.
- New ahos_core/ahos/completion_db_guard.py installs two SQLite triggers through PersistentMissionQueue._init_schema, blocking any raw SQL UPDATE/INSERT into completed if result_json is missing, invalid, or says something other than completed. Existing old rows remain unchanged.
- This guard enforces STATUS/PAYLOAD CONSISTENCY ONLY; it does not establish independent QA/file evidence. Zero-step completed records remain possible and need a stricter proof/QA receipt policy.
- New release_gate check database_completion_guard verifies both actual triggers are present. A clean code merge is not evidence the running database has installed them.
- Deployment prerequisites: review the 6 overlapping files with DeepSeek owners, test migrations on a restored copy, obtain a verified backup + rollback plan, run the full suite, and perform a controlled rollout. Never install triggers directly on live while concurrent workers own the DB.
