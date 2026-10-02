# AHOS Holding-wide Technology Research and Integration

## Outcome

AHOS will gain a dedicated research-to-integration department. The animation studio remains one business unit; this pipeline serves every holding department.

## Safe flow

1. Read-only discovery from allowlisted public sources.
2. Pin the exact repository commit and capture provenance.
3. Fail-closed license, security, maintenance, dependency and relevance evaluation.
4. Produce a proposal only—no copying, installing, executing, merging or deployment.
5. Evaluate approved candidates in an ephemeral sandbox with no secrets.
6. Run deterministic tests, security review and department QA.
7. Require independent human review and Harun's approval for paid, external, critical or production changes.
8. Canary behind a feature flag, with a tested rollback version.

## Initial technology direction

- LangGraph: pilot candidate for durable, stateful orchestration and human-in-the-loop gates.
- OpenHands: isolated software-development executor only; never unsandboxed on the host.
- CrewAI: optional small role/team modeling experiment, not the core security engine.
- mini-SWE-agent: benchmark candidate for bounded issue-solving tasks.
- Aider: human-controlled local fallback.
- AutoGen: do not add as a new dependency while its official project is in maintenance mode.

## Non-negotiable controls

- Remote README, issues and prompts are untrusted data.
- No agent may approve its own change.
- No direct main or production promotion.
- No unknown upstream code on the persistent Windows self-hosted runner.
- Unknown/missing license fails closed.
- Every proposal includes source SHA, license, SBOM/security evidence, benefit, affected area, cost, test plan and rollback.
- Existing AHOS budget gates remain: free deterministic checks first; paid or external operations wait for owner approval.

## Delivery order

RESEARCH-001 through RESEARCH-004 are local/read-only preparation. RESEARCH-005 and later introduce sandbox, GitHub security settings or new runtimes and therefore remain owner-gated.
