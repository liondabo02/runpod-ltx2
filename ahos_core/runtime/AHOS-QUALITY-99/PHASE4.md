# AHOS-QUALITY-99 Phase 4

Branch: `program/AHOS-QUALITY-99-phase4-chatgpt`

## Resource admission

Real Windows memory snapshot:
- total visible memory: 16,070,388 KB
- free physical memory: 515,208 KB
- free ratio: ~3.2%

State: **CRITICAL**.

Per the quality-program rule, heavy local model work is suspended. Existing
Codex/Claude/Python/Node processes belong to potentially unrelated workflows
and are not terminated or preempted.

## Local agent/tool inventory

Verified without paid model-generation calls:
- Codex CLI 0.162.1
- Claude Code 2.1.292
- OpenCode 1.18.35
- Ollama 0.40.4
- ADB available
- Ollama models: qwen2.5-coder:1.5b, qwen2.5-coder:7b,
  nomic-embed-text:latest
- direct DeepSeek CLI: not found

A bounded local Qwen 1.5B response attempt produced no output before the
quality program terminated it. It is not promoted as a healthy reviewer route.

DeepSeek Harness historical evidence remains sandbox-only; production
integration is not approved. Therefore exact Codex–DeepSeek separation remains
OPEN and is not counted as proven.

## System Design Primer mapping

Reference: donnemartin/system-design-primer (master), including its task/message
queue, back-pressure, availability/failover, consistency/availability and
independent-scaling sections.

AHOS additionally requires:
- idempotency
- bounded concurrency
- health checks
- recovery
- data integrity
- observability
- owner/authority boundaries
- deployment rollback

Deployment/rollback production proof remains open, so architecture is not
promoted merely because source code exists.

## Concurrency fix candidate

The known Windows lock defect is in a shared file owned by another active
branch. This phase does not edit it. An isolated candidate demonstrates the
intended behavior: transient PermissionError is treated as bounded contention,
retried, and must still time out safely.

Integration gate:
1. shared-file ownership conflict cleared;
2. integrate portable retry in CodingSupervisorStore;
3. repeated Windows stress;
4. zero loss, zero duplicate claim, no lock exception.

## Repeated stress

GitHub-hosted isolated runners execute five rounds x 100 tasks x four synthetic
claimers. Windows local repetition remains suspended while memory is critical
and the shared lock defect is unresolved.
