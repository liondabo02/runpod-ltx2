# AHOS Project Execution Standard

This repository follows a completion-first execution standard for all autonomous and assisted work.

## Core rule

The marginal cost of completeness is low with AI, so finish the whole job whenever the permanent solution is within reach.

- Research before building.
- Prefer the real fix over a temporary workaround.
- Do not leave small dangling tasks open when they can be closed now.
- Test before claiming completion.
- Add or update documentation when behavior, setup, interfaces, or operational steps change.
- Deliver finished artifacts, code, tests, reports, or verified outputs rather than only plans.
- Do not call work "ready" while known blocking defects remain.
- Preserve owner gates for paid, external, destructive, publishing, credential, and irreversible actions.
- Never expose or serialize secrets.
- For paid external providers, validate locally first and minimize live calls.
- When a live paid call is required, make the scope explicit, require owner approval, and avoid automatic retries unless explicitly authorized.
- For production character/audio work, preserve age, gender presentation, role, continuity, provenance, language, and human-review constraints.

## Definition of done

A task is complete only when all applicable conditions are true:

1. The requested behavior or artifact exists in its final intended location.
2. Relevant automated tests pass.
3. The result has been validated against the actual acceptance criteria, not only unit-level assumptions.
4. Documentation or operational instructions are updated when needed.
5. No known blocking defect, dangling migration, temporary patch, or hidden manual dependency remains.
6. Paid or external execution remains behind explicit owner approval where required.
7. Reports and status text reflect the current state accurately; never report READY/SUCCESS for work that is only planned or partially complete.

If any condition is not met, report the exact remaining blocker instead of saying the task is ready.

## Animation Studio acceptance rules

For the AHOS Animation & Cartoon Studio specifically:

- Recurring character identity must remain stable across episodes.
- Character age and gender metadata must drive visual and voice generation.
- Child characters must not silently fall back to adult voices.
- Infant characters must use age-appropriate vocalizations rather than adult-like sentence speech.
- Episode-generated guest characters must be materialized before the final screenplay so their visual and voice plans exist before dialogue production.
- Non-talking animals use species-appropriate vocalizations; talking animals require an explicit talking-animal designation.
- Multilingual dubbing must preserve speaker identity and character fit.
- Canonical voice enrollment requires provenance plus human fit approval.
- Scenario -> cast -> character references -> voice plan -> screenplay -> shots -> render/audio jobs must be traceable end to end.

## Working style

When asked to implement something, default to completing everything that can be safely completed with available tools. Ask the owner only for actions that genuinely require owner input, credentials, payment approval, subjective human review, or access unavailable to the agent.
