# AHOS-QUALITY-99 — System Design Map

Reference orientation: the System Design Primer sections on task queues,
backpressure and failover. AHOS-QUALITY-99 maps those principles onto the
existing holding instead of introducing a second orchestration system.

| Principle | Existing AHOS mechanism | Evidence | Remaining gap |
|---|---|---|---|
| Authoritative asynchronous queue | CodingSupervisorStore / mission queue | durable 100-task stress | Windows lock contention under concurrent claim/finish |
| Backpressure | bounded live writer concurrency, queueing, max attempts | quality-program live writer concurrency = 1 | shared lock starvation must be fixed |
| Failover/recovery | leases + expiry/reclaim | actual two-process recovery E2E | production/unattended recovery still pending |
| Idempotency | idempotency keys on supervisor queue | replay stress | provider-side idempotency varies |
| Health checks | heartbeat/watchdog/runtime audit | monitoring rehearsal | long unattended production evidence |
| Failure isolation | worktrees/scoped paths/owner gates | worker E2E + separate quality worktree | shared-file ownership must remain coordinated |
| Least authority | A/B/C/D governance + RBAC | adversarial security audit | production secret-manager integration remains external |
| Cost isolation | CostGuard + zero-cost route policy | 0 USD audit | real DeepSeek route unavailable |
| Read-model consistency | Control Center reads authoritative runtime state | real create-task/dashboard flow | production fault consistency still needs long-run observation |

The quality program does not claim availability simply because these mechanisms
exist. Each row needs execution evidence, and known Windows lock contention
continues to block the concurrency criterion.
