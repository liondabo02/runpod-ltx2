# AHOS-QUALITY-99 Phase 2

Branch: `program/AHOS-QUALITY-99-phase2`

This phase remains isolated from active worker/dispatcher/control-center files.

## Measured starting score

The evidence-backed 15-area quality matrix starts at **64.00 / 100**.

This is not a success claim. The score is intentionally conservative:
- PROVEN = 1.0
- PARTIAL = 0.6
- UNMEASURED/BLOCKED = 0
- any unproven high-risk area blocks the 99% target

A four-worker Windows stress run reproduced a real lock-contention defect:
`CodingSupervisorStore._locked()` can receive `PermissionError` from the
lock-file create path. That shared file is currently owned by another active
branch, so Q99 records it as a blocking conflict rather than editing it in parallel.

High-risk open areas at phase start:
- real worker execution acceptance
- live crash/restart recovery
- file/data integrity recovery
- security adversarial integration
- real product acceptance

Android/browser is UNMEASURED and contributes zero.

## Phase-2 independent tasks

### Q99-010 Persistent-memory durability
Reopen the actual SQLite CodingMemory and verify:
- event persists after object/process-boundary reopen
- secrets are redacted
- repository recall is isolated

### Q99-011 State-integrity rehearsal
In isolated temporary state only:
- malformed JSON is detected
- hash tampering is detected
- healthy SQLite passes PRAGMA integrity_check
- damaged SQLite header is rejected

### Q99-012 Security adversarial audit
Verify:
- external action requires owner approval
- non-zero cost requires owner approval
- destructive/privileged action requires owner approval
- worker role cannot approve external/privileged action
- prompt override, secret request and guard-bypass patterns are detected

### Q99-013 Zero-cost audit
Verify daily budget 0 rejects every positive cost and model routing excludes paid endpoints.

### Q99-014 Monitoring rehearsal
Verify stale heartbeat produces restart candidate, healthy heartbeat is accepted,
and 99% error-budget breach is surfaced.

## Explicit non-claims

This phase does not prove:
- real Codex/DeepSeek provider execution
- actual Android device operation
- actual browser critical flow
- full studio release acceptance
- production deployment
- live process restart recovery


## Phase-2 measured progress

After the isolated memory, integrity, security and monitoring proofs pass, the
evidence score becomes **74.67 / 100**. This still does not satisfy the target.
Concurrency, live recovery, real worker execution, real product acceptance and
Android/browser evidence remain open.
