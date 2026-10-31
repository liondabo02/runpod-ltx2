# AHOS System Solver: CEO-to-Software Delivery Gate (v1)

## What is implemented

This increment connects the existing AHOS owner / CEO work-order registry to the existing software department coding supervisor. It preserves isolated Git worktrees, test-command policy, coding memory, limited retries and the explicit owner review gate.

1. The CEO/department manager opens a READY software work order with a coding capability.
2. The software manager supplies a scoped coding contract with an explicit Git repository, allowed paths and at least one acceptance test.
3. The existing WorkOrderCodingBridge dispatches the contract idempotently to the coding supervisor and marks the order IN_PROGRESS.
4. The coding worker executes within its isolated worktree; supervisor policies decide which tests may run; it produces a patch and review evidence.
5. A human owner explicitly approves or rejects the review evidence.
6. The new reconcile method syncs the terminal coding decision back to the work order. Approval evidence hash and reviewed patch hash are re-verified on reconciliation.

## State semantics

- QUEUED / RUNNING / WAITING_PROVIDER -> IN_PROGRESS (no completion claim).
- WAITING_OWNER_APPROVAL -> IN_PROGRESS (owner action still required).
- OWNER_APPROVED with matching evidence and patch digests -> COMPLETED.
- OWNER_REJECTED / RETRIES_EXHAUSTED -> FAILED.
- CANCELLED -> CANCELLED.
- Tampered or missing evidence -> an error and NO completion transition.

IMPORTANT: COMPLETED means an owner-reviewed *local patch* is ready for integration. It does not mean code was merged, deployed, published, or executed in production.

## CLI

Dispatch contracts and reconcile existing coding outcomes in the same call:

    ahos-coding-dispatch --work-orders /path/to/orders.json --coding-queue /path/to/coding.json --contracts-dir /path/to/contracts

Reconcile independently after an owner decision (without dispatching anything):

    ahos-coding-dispatch --work-orders /path/to/orders.json --coding-queue /path/to/coding.json --reconcile

Reconciliation can be scheduled during the CEO control center's existing status refresh. It is local state accounting, not a merge/deploy action.

## Verification

    python -m pytest -q ahos_core/tests/test_work_order_coding_bridge.py ahos_core/tests/test_ai_manager_planner.py

The new tests cover owner approval, rejection, evidence tampering, absent acceptance tests, malformed paths and contract types, and NaN/infinite manager cost estimates.

## Open-source inspiration and next stages

Agent design patterns considered: decomposition of work, tools/worktrees, bounded retries, independent verification, and evidence-gated completion. No proprietary weights are copied and Mistral Large 4 is NOT integrated or fine-tuned by this change.

Next stages are automatic CEO status reconciliation, classified failure/root-cause diagnostics, independent verifier agent, cost-aware multi-model routing and reproducible Mistral Vibe vs AHOS benchmark suites.

No secrets, production services, worker queues, other Git branches, or deployment configurations are changed by this PR.
