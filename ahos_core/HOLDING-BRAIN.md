# Holding brain: evidence coordination and self-improvement

`ahos.holding_brain` observes persisted coding and department queues, records concrete failures and recommends repair handoffs. It preserves the full holding requirements in its report; those requirements are `not_audited`, not assumed missing or complete. Queue counts never establish that the holding or a film is production ready.

From the repository's `ahos_core` directory:

```powershell
& $python -m ahos.holding_brain --runtime-dir "..\runtime" --repository ".."
```

Add `--dispatch` to enqueue scoped repair work for exhausted coding or department production failures. Existing coding workers perform the work in isolated worktrees, with tests and owner evidence gates. This does not merge, approve, pay, publish, install, or execute generated suggestions. Provider cooldowns are observations, not justification to retry early or select a paid model.

`runtime/holding-brain.json` contains observations, recommendations, repair queue handoffs and a bounded 50-entry decision history. Arbitrary task objectives, errors, provider bodies and credentials are not copied into this report. Source IDs are digests. Repair tasks use fixed versioned IDs and remain deduplicated across restarts; an exhausted repair is exposed for review rather than recursively creating new repairs or resetting the owner's decision.

The controller currently implements two evidence-based repair contracts. It is a foundation for autonomous coordination, not a general semantic reasoning model or a proof that every department can execute business operations. Internet research, dependency adoption, repository license evaluation and PC control are separate capabilities; they remain disabled here. It cannot know unseen runtime facts or replace human review of voice, character identity and final outputs.

For continuous use, call `run_brain_cycle(runtime_dir, repository, dispatch=...)` from the authorized company loop. Do not launch an additional independent loop for the same queues. Use a verified repository and Python environment. If the known scope files are absent, the handoff is reported `blocked_missing_scope` and nothing is queued.

## Enable the company integration

After installing this commit and gracefully stopping the existing company service,
run from `ahos_core` with the project's Python executable:

```powershell
& $python -m ahos.department_activation --runtime-dir "..\runtime" --allow-external --enable-brain
& ".\scripts\Start-AHOS-CompanyService.ps1" -PythonExe $python
```

This preserves coding configuration and enables one background observation cycle
every five minutes. The company service now rejects a second company loop using
an OS file lock. It must not coexist with an older pre-lock company process.
The dashboard's Holding Brain section displays observations, automatic dispatch,
GitHub watch status and the unconnected PC capability honestly.

The optional GitHub watcher reads only public metadata for the six reviewed
repositories in `docs/holding-upstream-candidates.json`. It checks daily, retries
failed checks hourly and queues research drafts when metadata changes. It neither
installs nor copies upstream code. License and exact revision must be reviewed
before adoption. See `docs/HOLDING-UPSTREAM-REVIEW.md` for integration tradeoffs.
Builder failures now save bounded, redacted diagnostics beside the attempt
worktree, outside the directory whose changes become the proposed patch.
