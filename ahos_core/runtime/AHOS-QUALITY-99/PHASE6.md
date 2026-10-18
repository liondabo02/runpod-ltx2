# AHOS-QUALITY-99 Phase 6

Branch: `program/AHOS-QUALITY-99-phase6-chatgpt`

## Q99-022 — Bounded unattended CompanyService soak

The actual AHOS CompanyService event loop runs for ten seconds in a temporary,
isolated runtime on the GitHub test runner.

Acceptance:
- repeated fresh heartbeat timestamps
- no error heartbeat state
- heartbeat observation gap <= 1 second
- clean stop
- no external provider, paid API, production queue, shared port or publishing

Ten seconds is a bounded soak test, not a claim of multi-hour production uptime.

## Q99-023 — Machine-readable blocker registry

`BLOCKERS.json` makes the remaining 99% blockers explicit and prevents a
summary/reporting layer from silently treating them as completed.

## Q99-024 — Performance-aware assignment audit

Read-only source audit found:
- current feature branch VirtualWorkforceRegistry orders by available slots,
  spend and worker_id;
- it does not consume historical success/QA performance;
- another isolated local worktree contains worker_metrics collection code, but
  that work is not merged into feature/ahos-autopilot and still does not alter
  the current registry's ranking.

AHOS-QUALITY-99 does not edit that other worktree. The integration stays an
explicit blocker until performance evidence actually changes assignment.
