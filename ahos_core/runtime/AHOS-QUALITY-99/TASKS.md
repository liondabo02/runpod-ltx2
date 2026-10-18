# AHOS-QUALITY-99 Task Ledger

## Q99-004 — Restart/recovery fault matrix
Status: IMPLEMENTED / CI PENDING
- Isolated temp queue only.
- Injects an expired worker lease.
- Verifies a different worker can reclaim after simulated restart.
- Verifies idempotent replay and zero task loss.

## Q99-005 — Dashboard truth auditor
Status: IMPLEMENTED / CI PENDING
- Read-only comparison of queue counts/task IDs against dashboard coding read model.
- No dashboard files or ports are modified.

## Q99-006 — Worker-performance evidence model
Status: IMPLEMENTED / CI PENDING
- Ranks workers using success, independent QA, latency, and retries.
- Does not change current dispatcher/assignment code while parallel agents may own it.

## Q99-007 — Zero-cost builder/reviewer routing simulation
Status: IMPLEMENTED / CI PENDING
- Requires builder/reviewer separation.
- Rejects non-zero estimated-cost providers.
- Makes no API calls.

## Q99-008 — Android/browser proof contracts
Status: IMPLEMENTED / CI PENDING
- Defines strict evidence needed before Android/browser can be counted as proven.
- Does not fake device/browser evidence.

## Q99-009 — 100-task synthetic concurrent queue stress
Status: IMPLEMENTED / CI PENDING
- Four synthetic claimers against an isolated queue.
- This is not a production concurrency increase; live writer concurrency remains 1.
- Acceptance: exactly 100 unique claims, no duplicate claim, no lost queue record.
