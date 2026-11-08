# Persistent coding worker: recovery and retry context

The Miniverse worker retains the existing task workspace across retries. A retry now
includes its attempt number and the preceding error (bounded to 4,000 characters)
in the pipeline instruction, marked as untrusted diagnostic data. The builder is
asked to inspect existing edits and tests before repairing the cause.

SQLite queue writes reject expired leases. The worker supplies the attempt number
to heartbeat, completion and failure calls, so an old attempt cannot overwrite a
new attempt even when both processes use the same owner name. Legacy callers may
omit the optional `attempt` keyword; they do not receive that generation check.
Lease time is checked after acquiring the write lock. Polling also marks expired
final attempts failed rather than leaving them permanently running. No database
schema migration is required.

Execution and heartbeat are monitored together. Losing the lease cancels the
cooperative async executor and prevents stale completion. Cancellation cannot kill
an already running synchronous function inside `asyncio.to_thread`; the current
OpenHands pipeline uses such a thread. Hard interruption of that builder still
needs a supervised subprocess. These changes do not claim to solve that gap or
provide a filesystem sandbox for model-generated commands.

The pipeline SDK is loaded when a PipelineTaskExecutor is created without an
injected pipeline. Queue/status operations no longer load it merely by importing
the worker module.

`MINIVERSE_OPENHANDS_MAX_ITERATIONS` configures the builder's SDK step limit, from
1 through 500. The default remains 12. The setting takes effect in a newly started
process; it is not an unlimited execution mode, an increased API budget or a
wall-clock timeout. No provider, credential, billing setting or live service was
changed for this delivery.

Validation uses offline fixtures: real temporary SQLite databases, async workers,
simulated crashes/lease transfer/database contention, and mocked SDK/model calls.
It is not a live Codex/DeepSeek coding qualification. Evidence is saved under
`ahos_core/runtime/artifacts/worker-engine-20261018/`.

Run the focused suite from control_plane_v2 with its existing Python environment:

```text
python -X utf8 -m pytest tests/test_persistent_worker.py tests/test_worker_recovery.py tests/test_execution.py tests/test_openhands_builder.py tests/test_openhands_sdk_compat.py tests/test_builder_iteration_config.py -p pytest_asyncio.plugin -p no:cacheprovider --basetemp=<new-writable-test-directory> -q
```

Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for the controlled test environment. Do not
reuse a live task database for tests. Existing worker processes need a controlled
restart to import new source; this delivery does not restart them.
