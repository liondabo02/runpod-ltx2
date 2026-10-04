# Autonomous department draft production

The department runner adds real AI artifact production for software, quality,
research, infrastructure, data, creative, marketing, sales, finance, operations
and support. It does not pretend that a roster of 22 profiles is a deployed team.

## Start without interrupting an existing coding attempt

From the repository root, run `ahos_core/scripts/Start-AHOS-Departments.ps1`
with `-PythonExe` pointing to the existing Python environment. The script reads
OPENROUTER_API_KEY from the current or persisted user environment without printing
it. It preserves the coding configuration and queues eleven idempotent bootstrap
jobs. Only free OpenRouter models are accepted, with a zero-price provider cap.
Credentials are never stored in configuration. External generation is explicitly
enabled by this startup action.

A standalone scheduler starts, so an old company process need not be killed.
New company processes also poll the departmental queue before blocking coding
work. Queue locks prevent duplicate task claims. Independent tasks use up to
three concurrent provider requests; dependent tasks consume evidence-checked
upstream drafts. Provider timeouts are finite; retries are bounded to three task
attempts. Provider availability and free-model rate limits can still block work.

Restart only the panel process to load the new Department Work interface.
Use it to queue a department objective, inspect the full artifact, and approve or
reject the exact artifact hash. Approval applies only to the draft: it does not
publish, authorize spend, contact prospects, apply code or deploy infrastructure.
Drafts that depend on rejected or changed evidence cannot be approved.

## Where to inspect

- Panel `/api/status`: `departments.tasks` and task status/attempts/errors.
- `runtime/departments/department-queue.json`: persisted tasks.
- `runtime/departments/department-artifacts`: full generated deliverables.
- `runtime/department-service-status.json`: scheduler outcome.
- `runtime/departments-error.log`: standalone startup errors.

## Honest scope

Software produces implementation specifications; the existing coding supervisor
still handles actual isolated code changes and tests. Research produces briefs
with verification needs, not claims of live sourced research. Creative drafts do
not constitute rendered episodes. Finance does not perform transactions. Sales,
marketing and support do not send messages. General outputs pass structural
checks and await owner review, not a claim of professional-quality verification.
Existing studio render/TTS/publishing and owner gates are preserved.

This change makes departments useful in parallel at preparation work. Full
end-to-end departmental execution still requires purpose-specific executors and
validated outputs; it is not evidence that the complete holding is finished.

## Project-grounded briefs

Activation now embeds a curated AHOS brief in every objective: autonomous holding,
Python/HTML panel, persistent tasks, isolated coding, recurring cartoon identities,
seven-language planning and explicit evidence/owner gates. It names unknown inputs
and forbids inventing an AHOS acronym or treating it as an asset-management ERP.
The objective carries this context even when an older scheduler is still running.

The old `DEPT-BOOTSTRAP-*` tasks are marked `superseded` unless already approved or
rejected. Original artifacts and decisions are retained. New `DEPT-GROUNDED-*`
tasks regenerate all departmental drafts and downstream dependencies from the
project brief. Activation is idempotent and does not reset coding tasks.

Grounding improves task relevance; structural checks do not constitute semantic
quality approval. The owner must still review whether proposals match the project.
