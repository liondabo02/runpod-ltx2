# AHOS 99% Proof Bundle

This branch is intentionally isolated from the existing AHOS 99% improvement
branches. It does not edit their conflict-safety, failure-triage,
requirement-audit, creative-acceptance, or final-gate files.

## What it adds

- Hash-bound production evidence records.
- Freshness checks for production evidence.
- Same-commit / same-platform proof enforcement.
- A fail-closed proof bundle covering:
  - deployment
  - unattended autonomous runtime
  - restart/recovery
  - studio acceptance
  - identity acceptance
  - language acceptance
- A safe adapter catalog for locally installed/open-source tools.
- A read-only recovery-rehearsal evaluator.

## Why

AHOS must not claim 99% maturity because code exists or unit tests pass.
Production evidence must be independently observable, fresh, immutable by hash,
and tied to the exact commit being accepted.

The adapter catalog is deliberately descriptive. Registering a tool does not
execute it, grant it repository access, authorize networking, spend money, or
bypass owner approval.

## Integration rule for downloaded tools

Each locally installed tool must be registered with:

1. capability
2. trust tier
3. sandbox requirement
4. network requirement
5. repository-write authority
6. owner-approval boundary

Experimental tools remain ineligible for autonomous execution until reviewed.
