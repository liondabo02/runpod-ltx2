# AHOS-QUALITY-99 Phase 4

## Policy correction: automatic-test coverage

The full AHOS repository line coverage has not yet been measured in a valid
complete isolated checkout. The sparse-checkout full-suite coverage attempt was
stopped because omitted project paths caused unrelated failures.

Therefore the automatic-tests area must remain PARTIAL until a valid full
coverage measurement exists. The AHOS-QUALITY-99 namespace itself reached 95%
line coverage, but that cannot be substituted for whole-holding coverage.

This correction lowers the evidence score from 86.67 to **84.00 / 100** before
new Phase-4 proofs. This is intentional: unmeasured areas are not completed.

## Q99-020 — Architecture invariants

Verify existing, not-new:
- owner authority boundary
- localhost-only Control Center
- hard 0 USD boundary
- durable 100-task queue semantics
- actual process-boundary recovery

## Q99-021 — Bounded soak

Manual acceptance target:
- 10 queue rounds x 100 tasks = 1000 task operations
- 5 process-recovery rounds
- zero queue failure
- zero recovery failure
- no external API/provider
- no production state

## System Design Primer mapping

See SYSTEM-DESIGN-MAP.md. AHOS keeps one authoritative queue/control plane and
uses queues, bounded retries/backpressure, leases/failover, idempotency and
health checks rather than introducing a competing orchestrator.
