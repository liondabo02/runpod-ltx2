# AHOS 99% Maturity Gate

This branch is deliberately isolated from feature/ahos-autopilot so parallel
owner workflows can continue without sharing an edit branch.

## Non-conflict rule

The coding supervisor reserves approved path scopes for running work and for
work waiting for owner review. A second task in the same repository may run
concurrently only when its allowed paths do not overlap.

Examples:

- src and src/api conflict.
- src/api and src/ui can run in parallel.
- identical paths conflict.
- the same path in different repositories can run in parallel.

The dashboard/status read model also exposes queued tasks blocked by active
scope reservations.

## 99% evidence rule

Source completeness is not enough to claim 99% maturity. The maturity scorer
hard-caps the reported score at 95% until deployment, unattended autonomous
runtime, and restart/recovery are independently PROVEN.

This prevents architecture or unit-test coverage from being reported as real
production readiness.
