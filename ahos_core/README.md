# AHOS Core — Autonomous Holding Operating System

AHOS Core is the safety-first operating core for the Miniverse digital holding.

## Autonomous AI writers' room

`ahos.autonomous_story_room.AutonomousWritersRoom` replaces manual screenplay
handling with a fail-closed writer/revision loop. A runtime-supplied AI adapter
writes complete episode packets and receives machine-readable corrections until
the draft passes deterministic checks for timing, scene and dialogue coverage,
infant/toddler speech, repetition, visual action, originality, and approval
boundaries. Every attempt and accepted-story fingerprint is persisted in SQLite,
so later episodes cannot silently repeat an earlier story.

The room produces review-ready stories only. It cannot approve its own work,
spend money, render, publish, or contact an external provider by itself. The
holding runtime must inject a model adapter through the existing governance and
budget gates.

Run a free, explicitly enabled external writers' room against an existing
canonical character database:

```bash
ahos-story-room --output ../runtime/story-room --characters-db ../runtime/studio-rehearsals/S01E001-professional/state/characters.db --episode 2 --topic "Uçurtmanın kayıp kuyruğu" --learning-goal "sabır ve yardımlaşma" --model openrouter/free --allow-external
```

The command can revise a rejected draft up to four times. It writes the accepted
review packet, episode versions, originality fingerprints, and every failed QA
attempt under `--output`. Paid models additionally require
`--owner-approved-paid`, a positive estimated per-call cost, and a sufficient
daily budget. No story is owner-approved automatically.

## Professional episode rehearsal

Generate a local, traceable eight-minute studio rehearsal without paid or
external execution:

```bash
python -m ahos.production_rehearsal --output ../runtime/studio-rehearsals/S01E001
```

See [docs/PRODUCTION_REHEARSAL.md](docs/PRODUCTION_REHEARSAL.md) for the evidence
contract, owner approval flow, and remaining production gates.

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
