# AHOS-QUALITY-99 — Program State

Program: **AHOS-QUALITY-99**  
Isolation branch: `program/AHOS-QUALITY-99`  
Base: `feature/ahos-autopilot@d724de3a34b29ef9e45b46f47c42554b3d02f09a`  
Paid API budget: **0 USD**  
Initial writer concurrency: **1**  
Production mutation: **disabled**  
Automatic publishing/deployment: **disabled**

## Isolation evidence

- Program uses its own branch.
- Quality-program implementation is under `ahos_core/ahos_quality99/`.
- Quality tests are under `ahos_core/tests/quality99/`.
- Program evidence is under `ahos_core/runtime/AHOS-QUALITY-99/`.
- Active branch `improve/ahos-99-conflict-safety` currently edits
  `ahos_core/ahos/coding_supervisor.py`; AHOS-QUALITY-99 therefore does not edit
  that shared file until the conflict is resolved.
- No force merge, production deployment, paid API call, queue mutation, port
  change, or service restart is performed by this program.

## Baseline measurement policy

No area is counted complete without evidence. `UNMEASURED` contributes zero,
and high-risk areas block a 99% claim until independently proven.

| # | Area | Start state | Verification | Current gap | 99% success criterion |
|---|---|---|---|---|---|
| 1 | Architecture reliability | PARTIAL | AHOS CI, requirement/final gates | integrated production proof still pending | merged architecture gates + independent runtime proof |
| 2 | Agents doing real work | PARTIAL | coding/studio evidence records | real unattended acceptance not proven | real scoped task completes + independent QA |
| 3 | Persistent task queue | PARTIAL | durable JSON/SQLite + 100-task synthetic stress | higher concurrency/fault matrix pending | 0 duplicate/loss across required stress/fault cases |
| 4 | Crash recovery | PARTIAL | leases/recovery modules | live restart rehearsal pending | interrupted task resumes/requeues with evidence |
| 5 | Concurrent task safety | PARTIAL | path-scope conflict logic | active parallel branch owns shared supervisor code | no overlapping writes in concurrency/fault tests |
| 6 | File/data integrity | PARTIAL | atomic queue writes, hashes, provenance | restore rehearsal pending | corruption/restore tests pass; no silent truncation |
| 7 | Codex–DeepSeek routing | UNMEASURED | adapter catalog only | end-to-end dual-agent evidence absent | deterministic routing + reviewer separation proven |
| 8 | Automatic tests | PARTIAL | GitHub CI 3.12/3.13/3.14 | load/fault/android/browser gaps | critical unit+integration+load+security suites green |
| 9 | Security/authorization | PARTIAL | RBAC, approval gates, prompt guard | adversarial integration evidence incomplete | no owner-gate bypass in security suite |
|10 | API/token cost | PARTIAL | cost guards and 0-USD program rule | provider failover cost telemetry incomplete | 0 paid calls in quality program + bounded free fallback |
|11 | Persistent memory | PARTIAL | coding/holding/localization memories | restart + corruption evidence incomplete | durable recall survives restart and rejects corrupt state |
|12 | Presidential dashboard | PARTIAL | control-center health/read model | consistency under faults not independently proven | dashboard equals queue/runtime truth in fault scenarios |
|13 | Real product production | PARTIAL | studio pipeline modules | STUDIO-005..008 real acceptance incomplete | actual release candidate passes acceptance chain |
|14 | Android/browser validation | UNMEASURED | no qualifying current proof found | device/browser E2E absent | repeatable Android + browser smoke evidence |
|15 | Monitoring/logging/retry | PARTIAL | heartbeat, metrics, retries, watchdog | SLO/error-budget operational proof incomplete | failure injected, detected, retried/recovered, reported |

## Task ledger

### Q99-001 — Isolation and baseline
Status: COMPLETED  
Changed files: quality-program namespace and this state file.  
Evidence: separate branch; active shared-file conflict detected and avoided.  
Remaining risk: local machine worktree/process ownership has not yet been
independently inspected from this Git-only execution surface.

### Q99-002 — Bounded worker process primitive
Status: IMPLEMENTED; CI verification pending  
Problem: current shared coding supervisor invokes a builder through a blocking
subprocess boundary without a dedicated quality-program cancellation/timeout
primitive. The shared supervisor file is currently owned by another active
branch, so direct integration is intentionally deferred.  
Fix: isolated `BoundedProcessRunner` with timeout, cooperative cancellation,
process-group termination and forced kill fallback.  
Success criterion: normal completion, timeout and cancellation tests all pass.

### Q99-003 — 100-task synthetic durable-queue test
Status: IMPLEMENTED; CI verification pending  
Scope: local temp directory only; no external API and no production queue.  
Checks: 100 unique enqueues, idempotent replay, 100 claims, 100 terminal
outcomes, zero duplicate records, zero lost records.

## Next independent tasks

1. Run CI and record exact test evidence.
2. Build restart/recovery fault matrix in the quality namespace.
3. Build dashboard-vs-queue consistency auditor without modifying control-center.
4. Build agent-performance assignment evidence model without touching active
   dispatcher files.
5. Build zero-cost Codex/DeepSeek routing simulation and reviewer-separation
   tests.
6. Build Android/browser proof contracts and local smoke harnesses; real device
   evidence remains pending until an execution surface/device is available.


## Verification log — 2026-10-18

### Local isolated worktree
- Existing worktree `C:\\actions-runner\\_work\\ahos-quality-99` belongs to another workflow on `quality-99/ahos`; untouched.
- Main checkout `feature/agent-control-plane` had active modified/untracked files; untouched.
- AHOS-QUALITY-99 created separate worktree `C:\\actions-runner\\_work\\AHOS-QUALITY-99-chatgpt` on `program/AHOS-QUALITY-99`.
- Initial sparse-checkout pattern write used the wrong worktree `.git` assumption; corrected with worktree-local `git sparse-checkout set`.

### Test evidence
- Incorrect root-level command: `python -m pytest -q ahos_core/tests/quality99` -> 9 collection errors because `ahos_core` was not the Python working directory. Recorded as operator-command error, not counted as pass.
- Correct local command from `ahos_core`: `python -m pytest -q tests/quality99` -> **15 passed in 9.24s**.
- GitHub AHOS Core CI on head `6612da78...`: Python 3.13 PASS, Python 3.14 PASS, Python 3.12 FAIL.
- Python 3.12 failure: 3 bounded-process tests failed because `subprocess.communicate()` attempted to flush an already closed stdin on POSIX.
- Fix: after manually closing child stdin, clear `process.stdin` before `communicate()`. No shared AHOS worker file changed.
- Re-verification: pending new CI.
