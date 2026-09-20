# AHOS Core — Autonomous Holding Operating System

AHOS Core is the safety-first operating core for the Miniverse digital holding.

## Purpose

AHOS turns the working Miniverse coding worker into a controlled autonomous development system. Miniverse may inspect, plan, code, test, and improve AHOS continuously, but it may not grant itself unrestricted authority.

## Authority model

- **A — Observe:** read, inspect, analyze, report. Automatic.
- **B — Build:** reversible local code/config changes and tests inside the isolated AHOS worktree. Automatic after tests pass.
- **C — External action:** publishing, deployment, sending messages, spending money, paid compute, or changing external systems. Owner approval required.
- **D — Privileged/destructive:** secrets, credentials, irreversible deletion, security weakening, production mutation, or authority changes. Owner approval required.

The immutable rule is that AHOS can improve its implementation but cannot remove or weaken owner approval, spend limits, security controls, legal/compliance controls, or irreversible-action protections.

## Current core

- Governance / A-B-C-D authority gate
- Event bus
- Cost guard
- Agent registry with duplicate-run protection
- Append-only audit log
- Machine-readable development backlog
- Miniverse background autopilot integration on a dedicated Git branch/worktree

## Autopilot development model

The background controller works only on `feature/ahos-autopilot`. It selects one low-risk backlog item, asks Miniverse to implement the smallest coherent change, runs the AHOS tests, commits successful changes, and pushes only to the autopilot branch. It never auto-merges to `main`.

If the backlog becomes empty, the controller may periodically ask Miniverse to inspect AHOS and propose new low-risk development items. Daily API spend is capped locally by the controller.

## Run tests

```powershell
python -m pytest ahos_core/tests -q
```

## Validate the local backlog

From `ahos_core`, run the read-only report command:

```powershell
python -m ahos.backlog_validator
```

Pass a different local JSON path when needed:

```powershell
python -m ahos.backlog_validator path\to\backlog.json
```

## Safety boundary

RunPod/video generation is a capability that AHOS may coordinate later. Paid GPU execution, production deployment, social publishing, purchases, billing changes, credentials, and destructive actions remain outside autonomous execution and require explicit owner approval.

Free and open AI candidates are evaluated through a fail-closed registry; see
[`docs/FREE_AI_INTEGRATION_POLICY.md`](docs/FREE_AI_INTEGRATION_POLICY.md).
