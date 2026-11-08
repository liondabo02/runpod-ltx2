# AHOS TaskBoard — Safe Owner, Lease, Handoff

This file-backed contract coordinates Codex and DeepSeek workers using the **same taskboard.json** on one host. It does not automatically intercept unrelated queues or cloud agents; integration at the worker dispatcher is required.

## State and transition model

- queued -> claimed -> running -> done (with evidence) or blocked (with reason)
- handoff: claimed/running -> claimed by a DIFFERENT owner, atomically
- release: claimed/running -> queued
- expiration: previous owner's heartbeat, completion, release and handoff are rejected; any worker may reclaim

The JSON persists `history` events recording who claimed, started, handed off, released, completed, or blocked each task. Repeated active tasks with the same `dedupe_key` use the existing task rather than creating a duplicate.

## Example (PowerShell in ahos_core)

```powershell
$board = 'C:\ahos-data\taskboard.json'
python -m ahos.taskboard --board $board add 'Mipiluna smoke tests' --key 'mipiluna:smoke-test'
python -m ahos.taskboard --board $board claim codex --lease 900
# Supply task ID shown by command:
python -m ahos.taskboard --board $board heartbeat TASK_ID codex --lease 900
python -m ahos.taskboard --board $board handoff TASK_ID codex deepseek --lease 900
python -m ahos.taskboard --board $board history TASK_ID
python -m ahos.taskboard --board $board complete TASK_ID deepseek --evidence 'pytest: 12 passed' --file 'src/game.py' --test 'pytest tests/test_game.py'
python -m ahos.taskboard --board $board list
```

Workers can also use `release TASK_ID OWNER` or `fail TASK_ID OWNER REASON`. The same stable `--key` prevents duplicate active jobs. A key may be reused for new work after the previous task becomes terminal.

## Important operating conditions

1. Give every independently operating worker instance a unique owner ID; two processes with the same ID are treated as one owner.
2. Workers must renew their leases and verify ownership **before writing code or performing an external action**; use isolated Git worktrees for separate code changes.
3. The OS file lock only protects the taskboard JSON. It is NOT a cross-machine lock. Cloud workers must share a transactional service/database to coordinate safely.
4. Task completion requires evidence but does not independently run the claimed test. Keep existing CI and human approval gates.
5. Never bypass AHOS spending, deployment, security, or owner approval rules.
6. Malformed board data now fails closed instead of silently being reset.
7. The module is a contract, not a turnkey integration with existing AHOS queues. The next step is to call the API from each dispatcher/worker before task execution.

Run `python -m pytest -q tests/test_taskboard.py tests/test_report.py` to verify.


## Integrated AHOS mission route (24 October 2026)

`OwnerConsole` now passes `runtime_dir/taskboard.json` into the mission orchestrator.
Each mission step is claimed by its stable `mission_id:step_id` before a worker
starts. A separate heartbeat renews the lease while the worker runs. Independent
QA results and artifact paths are saved before the task is marked `done`.
Duplicates or blocked tasks fail closed; owner-approval pending tasks return to
the queue without bypassing approval. Each deployment/runtime using a different
runtime directory has its own board. Standalone Codex or DeepSeek sessions that
do not invoke AHOS OwnerConsole are not yet automatically tracked.

## Browser release gate

For web projects `project_qa` launches installed Edge/Chrome in headless mode.
A missing browser, failed document, blank rendered page, known fatal overlay, or
browser stderr JS exception blocks a web delivery. Non-web projects use the
existing independent static/integrity review. The browser smoke does not prove
full UX or interaction quality: add project-specific click/navigation tests for
each application before public release. Tests explicitly set
`AHOS_BROWSER_QA=0` to avoid launching browsers in the unit suite; production
should leave browser QA enabled.

Manual real-Edge verification:
`python -c "import runpy;runpy.run_path('scripts/browser_gate_real_probe.py')"`
