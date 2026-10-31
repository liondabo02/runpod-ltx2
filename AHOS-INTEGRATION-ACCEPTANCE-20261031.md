# AHOS Consolidation and Production Acceptance — 2026-10-31

STATUS: NOT READY FOR LIVE DEPLOYMENT. This report is evidence from an isolated local Git worktree, not an instruction that DeepSeek has received or accepted.

## Ownership and isolation
- Live worktree: C:\actions-runner\_work\runpod-ltx2\runpod-ltx2, branch feature/agent-control-plane. Dirty state: 191 uncommitted paths observed. Do not reset, modify, or mass-stage.
- DeepSeek Harness was active (22 related processes); never terminate those sessions, edit their locks, restart daemon, or mutate queues without an explicit separate owner decision.
- Consolidation worktree: C:\actions-runner\_work\AHOS-CONSOLIDATION-20261031, branch fix/ahos-consolidation-20261031.
- Combined 11 prior isolated reliability / model / delivery / QA commits via fast-forward and added source provenance and blocked-task triage commits.
- For testing only, approximately 40 live-only Python modules and an adapter package were copied into the separate worktree UNTRACKED. These are neither integration-ready nor approved for staging; DO NOT use git add -A.

## Measured blockers (read only)
- Live company-service.db: 312 blocked, 297 cancelled, 200 completed in the snapshot reviewed. Counts may change; recheck before decisions.
- Latest 30 missions were blocked; 244 blocked missions had broad QA/acceptance rejection labels; 68 had other generic error labels.
- Of 312 blocked mission payloads, last step = blocked for 279; no recorded step for 33.
- QA summary text is too generic to distinguish these 244 root causes by conservative keyword classification. Do not guess or mass-resolve them.
- Daemon was observed idle / no suitable mission; the UI returning HTTP 200 is NOT verified code delivery.
- In the Git source, an internal import dependency on studio_department.py is not tracked. A clean checkout can fail despite a developer's working copy running normally.
- This branch's new source integrity gate detects untracked or absent direct internal modules. The live/isolated test copy is not a release artifact.

## Implemented, kept separate
- Consistent SQLite WAL snapshots, SHA-256 manifests, test proofs and no known secrets in runtime ZIP selection.
- Read-only fail-closed release gate with queue, delivery, source provenance, Git cleanliness, backup and test evidence checks.
- Bounded local genuine model response preflight and opt-in free local fallback; no silent paid provider calls.
- SHA-256 content-backed delivery tracking; no trust in worker self-report, mtime touch or truncated scans; no deletion-only success.
- Worker completion rate tied to independent QA; crashes release leases and mismatched worker/QA task IDs are rejected.
- Read-only blocked-task triage with redacted category and last-step breakdown. Never writes to live database.

## Acceptance required BEFORE a production merge
1. DeepSeek/owner reconcile live dirty files and identify authoritative owners. Preserve changes, do not delete or cherry-pick blindly.
2. Commit/review studio_department.py and any transitive internal dependencies with explicit ownership and code review; run a clean checkout CI.
3. Fix QA feedback to retain structured machine-actionable failure codes and independent acceptance evidence, not only 'QA rejected'.
4. Demonstrate a fresh sample of >=30 real tasks with consistent diff, test stdout and separate QA; improve new-sample completion rate >=90%, without rewriting old blocked/cancelled history.
5. Unblock or explicitly retire existing tasks according to owner-approved policies; no mass reset or silent retries.
6. Run the complete test suite in a clean reproducible environment; isolate hanging/network tests and ensure no unexplained failures.
7. Complete restore drill and owner approval with zero destructive changes to active runtime; verify rollback procedure.
8. Deploy only a reviewed, versioned, easily reversible build and monitor a new production sample.

## Developer test commands
From worktree/ahos_core:
python -B -m pytest -q tests/test_backup.py tests/test_release_gate.py tests/test_source_integrity.py tests/test_blocked_triage.py tests/test_provider_preflight.py tests/test_providers.py tests/test_delivery_integrity.py tests/test_daemon.py tests/test_verified_worker_metrics.py tests/test_worker_runtime.py tests/test_worker_metrics.py tests/test_ceo_knowledge.py --tb=short
python -B -m ahos.blocked_triage --database C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\company-service.db

Do not mark this project '100% complete' until every critical acceptance item is independently confirmed.