# AHOS Agent Growth — evidence-based continuous improvement

## Implemented controls

- Owner: deployment identity fixed to `harun` in `ahos.sovereign`; corrupt or different-owner pledges fail closed. This is a local code policy, not cryptographic authentication. Privileged endpoints must additionally be protected by authenticated operator access.
- All 81 rostered workers have persistent operational minds; growth overlays are stored separately under `runtime/minds/growth/<worker>.json` to avoid interfering with other mind writers.
- QA-backed observations come from SQLite read-only. Completed work must have independent QA and verified delivery. Failed-step reflections require an observed blocked/failed step and an explicit failure reason.
- The engine examines nine workers per cycle using a durable cursor, covering 81 workers in nine cycles. It never generates, cancels, completes or requeues missions.
- Emotions are simulated operational signals (`curious`, `focused`, `cautious`, `under_load`) based on actual workflow pressure and outcomes; there is no claim of subjective feeling or sentience.
- Peer help references a successful mentor QA step and a real failure from a colleague in the same department. Assistance cannot grant new capabilities/permissions and is not counted as demonstrated skill gain.
- Failure lessons are deduplicated; older lessons are archived before leaving the bounded active window. Coaching is recorded in append-only `peer-support.jsonl`.
- Observed progress uses two windows of eight QA-backed steps; insufficient evidence is indicated explicitly, rather than inventing improvement or retraining.
- LLM prompts and idle study receive only allowlisted safe advice; no raw mission body or user-created messages can become privileged instructions.

## Harun's approval scope

Spending, publishing, deleting, credentials and privilege changes stay subject to the pre-existing explicit owner approval gates. No emotional signal, initiative, mentor or simulated self-learning may waive these gates. A matched name alone is *not* authentication. Use proper authentication and filesystem access control before any public API exposure.

## Queue limits

The separate queue-capacity implementation uses a hard 300-pending admission cap and resumes autonomous work with headroom below 240. Growth/learning does not enqueue and cannot inflate successful job counts. Cancelled work is not delivery.

## Verification

Run from `ahos_core`:

```powershell
python -m pytest -q tests/test_agent_growth.py tests/test_sovereign_evidence.py tests/test_self_learning_rotation.py
python -m pytest -q tests
```

Review `runtime/daemon-state.json` at `learning.agent_growth`, worker growth JSON files and `minds/growth/peer-support.jsonl`. The authoritative pending count is the SQLite `missions` table. Corrupted overlay files are preserved. A stranded `.growth.lock` should be investigated before manual removal. Never upload runtime secrets.
