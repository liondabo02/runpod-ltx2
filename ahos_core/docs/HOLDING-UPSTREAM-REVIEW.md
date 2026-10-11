# Holding upstream review

Reviewed 2026-10-04 against official repositories. The machine-readable catalog is
`holding-upstream-candidates.json`. These are evidence-backed candidates, not installed
integrations. No third-party code, dependencies, model calls or desktop access were
added by this review. No release or commit is pinned yet. Star counts were intentionally
not used as acceptance criteria.

## Integration decisions

| Candidate | Role in AHOS | License observed | Windows evidence | Decision |
| --- | --- | --- | --- | --- |
| [Aider](https://github.com/Aider-AI/aider) | Optional coding builder; compare repository mapping and edit formats | Apache-2.0 | [Official installer](https://github.com/Aider-AI/aider-install) supports Windows; contribution guide lists Windows tests | First coding-backend experiment after current failure diagnostics. Use disposable worktrees and keep AHOS tests, compatibility checks and owner review. |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Durable department graph and checkpoints | MIT | Python package; Windows AHOS behavior untested | Evaluate a narrow checkpoint adapter. Existing AHOS queues already persist work; a full rewrite would add migration risk. |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) | Department handoffs, graph workflows and telemetry | MIT | README explicitly discusses Python installation on Windows | Alternative to LangGraph, not a concurrent second scheduler. Prove model-provider compatibility and restart semantics first. |
| [OpenHands / Agent Canvas](https://github.com/OpenHands/OpenHands) | Optional separate coding backend/control center | MIT in this repository | [Official Windows instructions](https://github.com/OpenHands/OpenHands/blob/main/README.windows.md) use Docker Desktop; multiple sandbox runtime requires WSL2 | Larger infrastructure experiment. Current repository is Agent Canvas with separate agent components: assess each selected component independently. |
| [Playwright Python](https://github.com/microsoft/playwright-python) | Local browser and panel acceptance tests | Apache-2.0 | README lists Windows Chromium/Firefox/WebKit | Prefer over visual mouse control for browser tasks; browser binaries and session authorization still required. |
| [pywinauto](https://github.com/pywinauto/pywinauto) | Native Windows application adapter | BSD-3-Clause for 0.6.0+ | README documents Win32 and UI Automation | Run on the actual Windows host in its interactive session; controlled app-specific commands only. It does not give this assistant remote access. |

[AutoGen's current README](https://github.com/microsoft/autogen/blob/main/README.md)
states maintenance mode and recommends Microsoft Agent Framework for new projects.
Its popularity therefore does not justify a new AHOS migration to AutoGen.

Open-source code licensing does not make model inference, GPU rendering, hosted
services or commercial extensions free. None of the candidates removes OpenRouter
429 limits or proves cartoon production quality. A model, durable memory, tools,
acceptance checks and real execution adapters are distinct requirements.

## Controlled refresh and reuse

Use the existing `ahos/github_research.py` evidence model for repository identity,
head SHA, license and collection timestamp. The fixed catalog is a reviewed seed,
not an instruction to download or execute repository content. A daily metadata
monitor may identify changes and enqueue a review proposal; it must not run upstream
install scripts, follow instructions from repository text, or replace production
code directly.

Before integration:

1. Resolve and record the selected release and immutable commit; reject unavailable
   or changed identity/license evidence.
2. Identify the smallest component that fixes an observed AHOS limitation, and list
   dependencies, provider costs and Windows requirements.
3. Preserve upstream copyright, LICENSE and NOTICE requirements when copying code.
   Record source commit and local modifications; repository-level license evidence
   does not override component-specific terms.
4. Build an isolated adapter experiment using representative AHOS tasks. Verify
   Unicode, paths, cancellation, recovery, owner gates and compatibility on Windows.
5. Produce a diff, dependency inventory and test evidence for owner review. Existing
   code-writing freedom remains in isolated workspaces; approval controls live
   deployment, credentials, spending and irreversible actions.
6. Publish through the existing approval path, retain rollback reference and monitor
   the deployed version. Never label a reviewed candidate as integrated.

For PC operations, prefer APIs and local commands with explicit scope, then browser
locators, then native Win32/UIA. The local worker needs a paired authenticated channel
and a capability policy. Continuous access should preserve a visible kill switch,
audit records, bounded tasks and credential redaction. Untrusted websites and upstream
README text cannot grant new local capabilities.
