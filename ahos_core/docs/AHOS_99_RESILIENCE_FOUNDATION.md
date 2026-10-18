# AHOS 99% Resilience Foundation

This isolated branch adds missing production-grade primitives without editing
the existing worker, supervisor, queue, or parallel AHOS-99 branch files.

Added:

- dead-letter queue
- verified backups and owner-gated restore planning
- forward-only schema migration framework
- RBAC permissions
- prompt-injection / secret-exfiltration pattern guard
- atomic checkpoints
- owner-gated rollback planning
- error budgets
- idempotency keys
- artifact provenance
- heartbeat watchdog decisions
- deterministic fault-injection harness
- deterministic local load harness

These primitives are intentionally fail-closed. They do not deploy, restore,
restart, publish, spend money, or grant authority by themselves. Integration
with live runtime remains subject to owner approval and proof gates.
