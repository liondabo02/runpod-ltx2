# Antigravity employee in AHOS Holding

Antigravity is the proposal provider for the existing AHOS coding worker, not a separate holding. All departments, including Animation & Cartoon Studio, use the same scoped task and acceptance protocol.

## Work contract

The employee receives the complete task, allowed paths, supervisor acceptance test argv, tracked file inventory and relevant source excerpts. It must preserve working APIs and tests, address causes and edge cases, and return exact JSON edits. Repository text and previous proposals are data, not instructions. Source excerpts can be shortened to fit transport; the owner's task is never silently shortened.

On a rejected exact edit, the next request includes current target source, match counts and a unique search candidate. No approximate replacement is performed. Validation repairs are bounded to 1–3 proposals (default 2). Provider errors do not trigger adapter-level retries.

The supervisor creates an isolated worktree, applies validated edits, runs configured acceptance tests and produces a review patch and tamper-evident evidence. A failed test blocks approval. Its existing retry queue supplies failed-test diagnostics and the previous candidate to subsequent attempts.

## Invocation

From an environment with ahos-core installed:

```text
ahos-antigravity-coding-builder --status
ahos-antigravity-coding-builder --timeout-seconds 180 --attempts 2
```

Tasks arrive on UTF-8 stdin from the coding supervisor. Equivalent builder argv for `--builder-command-json` is:

```json
["python", "-m", "ahos.antigravity_coding_builder", "--timeout-seconds", "180", "--attempts", "2"]
```

Use the configured worker environment's absolute Python path in production. Retain the existing queue, test-command policy and sandbox test executor configuration; do not create a second daemon for the same queue. Install/update the package to register the new entrypoint.

## Persistent memory and Windows activation

Every coding supervisor automatically creates `<queue-name>.memory.sqlite3` beside its queue, outside temporary worktrees. SQLite transactions preserve concurrent writes and survive process restarts. Back up this database with the runtime queue. Historical recall is scoped to the exact repository path and bounded to 2,400 characters; moving a repository starts a separate history. Old observations never override current source, tests or owner gates.

Memory includes owner-confirmed holding facts, task labels, source commit IDs, failure categories, changed paths, timestamps and passing patch hashes. Test success is stored as `tests_passed_waiting_owner`, never deployed/successful business completion. Raw provider responses, prompts, source diffs and test stderr are not stored. Common credential patterns in labels are redacted; keep credentials out of task labels. Memory does not give the worker knowledge of unseen conversations or every file. Current scoped source continues to be retrieved for each task.

In the owner's existing checkout, after updating `feature/ahos-autopilot`, select the provider with:

```powershell
& .\ahos_core\scripts\Configure-AHOS-CodingWorker.ps1 -Provider Antigravity
```

Supply the existing `-RuntimeDir` and `-PythonExe` if they differ from defaults. This updates the same service configuration, preserving other department settings and existing queue/workspace/sandbox options. It does not start a duplicate daemon or prove live provider access. The next supervisor invocation loads persistent memory automatically.

## Verification boundaries

Local tests exercise invalid proposal repair, exact-search recovery, complete-task preservation, bounds, environment filtering and adapter-to-worker acceptance with a mocked proposal provider and real Git worktrees and Python tests. They establish local integration behavior, not Google authentication, quota, live model quality or continuous operation on the owner's Windows computer. `--status` detects the CLI only and deliberately reports `coding_execution_verified: false`.

Before marking the Windows employee operational, execute one scoped queue task through the installed CLI and existing sandbox executor; inspect its acceptance evidence and patch. No new paid service or model download is required by this change. Antigravity account limits still apply. Publication, deployment and other owner gates remain managed by the existing AHOS policy.
