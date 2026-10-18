# AHOS-QUALITY-99 Phase 5

Branch: `program/AHOS-QUALITY-99-phase5-chatgpt`

Purpose: prove architecture reliability without mutating production.

## Q99-020 — Isolated staging deployment and rollback

The quality program performs a real filesystem deployment in a temporary staging
root:
1. content-address release v1
2. deploy and health-check v1
3. content-address release v2
4. upgrade and health-check v2
5. roll back to immutable v1
6. health-check v1 again
7. verify both artifact hashes throughout

Production mutation is explicitly false.

## Q99-021 — Actual CompanyService restart E2E

The real `ahos.company_service.CompanyService` event loop is started in a child
Python process against an isolated temporary runtime.

The test:
- waits for a real healthy heartbeat
- requests a clean stop through the isolated stop file
- confirms clean process exit
- starts a second process against the same runtime
- confirms a new healthy heartbeat timestamp
- stops the second process cleanly

No mission provider, paid API, production queue, shared port or external service
is involved.

## Architecture promotion rule

Architecture can move from PARTIAL to PROVEN only if:
- persistent queue/idempotency/back-pressure/bounded concurrency are represented
  in the architecture evidence model;
- health checks, recovery, integrity, observability and owner boundary are
  already proven by prior phases;
- this phase's staging deployment/rollback and real CompanyService restart tests
  pass on Windows and GitHub CI.

This is staging reliability proof, not production deployment authorization.
