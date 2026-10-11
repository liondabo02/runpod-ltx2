"""Curated project facts for department briefs; never credentials or guessed state."""
from __future__ import annotations
import json

PROJECT_CONTEXT = {
    'project': 'AHOS autonomous holding and animation studio',
    'meaning': 'Do not invent an expansion of AHOS or reinterpret it as an asset-management ERP.',
    'owner_goal': 'Departments perform work, inspect results, repair failures and prepare concrete outputs; the owner reviews approvals. Preserve the full holding scope.',
    'implementation_facts': [
        'The existing core is Python under ahos_core/ahos.',
        'The control panel uses Python http.server and HTML; no existing React frontend is established by this brief.',
        'Persistent company missions use SQLite and coding tasks use coding-supervisor-queue.json.',
        'Department drafts use a persistent queue and parallel generation with dependency evidence.',
        'The target currently shown is a Windows workstation, not a confirmed Windows Server installation.',
        'OPENROUTER_API_KEY comes from the environment; no credential values are supplied.',
    ],
    'requirements': {
        'HOLDING': 'Software, quality, research, infrastructure, data, creative, marketing, sales, finance, operations and support must cooperate with traceable task handoffs.',
        'CODING': 'Coding workers must implement requested changes in isolated worktrees, preserve existing public APIs/tests, run tests, repair failures and present evidence for owner approval.',
        'RELIABILITY': 'Persistent queues, bounded retries, observable errors, fresh heartbeat, backup and restart recovery. Do not assume a Windows Service has been installed.',
        'STUDIO': 'Produce an 8-minute preschool cartoon using stable recurring characters, screenplay, storyboard, animation, audio, dubbing, assembly and quality evidence.',
        'IDENTITY': 'Use supplied canonical character records. Child voices must match age; infants use vocalizations. Canonical images/voices require provenance and fit review. Missing approved cast data is a blocker, not permission to invent it.',
        'LANGUAGES': 'Studio plans cover Turkish, Kurmanci, German, Arabic, French, Spanish and English. Preserve speaker identity and character fit.',
        'OWNER_GATES': 'Preserve existing owner approval, cost, credential, publishing and destructive-action controls. Draft approval never authorizes payment, deployment or publication.',
        'EVIDENCE': 'Distinguish proposed capabilities, existing source-code facts, verified runtime outputs and missing evidence. Generated text alone never proves code, film or infrastructure was executed.',
    },
    'not_supplied': [
        'A current complete repository audit, installed-service inventory or latest production readiness report.',
        'Approved canonical visual and voice assets, provider prices or tested rendered episode evidence.',
        'Any requirement for vehicle assets, /assets/type=Vehicle, LDAP, React or PDF asset reports.',
    ],
    'output_rules': [
        'Write the owner-facing deliverable in Turkish; retain technical identifiers.',
        'For each backlog or runbook item identify the relevant requirement ID and the known file/system or missing input it concerns.',
        'Never present dependencies as ready unless evidence was supplied; do not assume services, schemas or UI libraries exist.',
        'Scope the deliverable to the requested department and this project. Do not create an unrelated generic enterprise template.',
        'Keep assumptions and blockers explicit. Proposed infrastructure options are proposals, not installed facts.',
    ],
}


def grounded_objective(objective: str) -> str:
    return objective + '\n\nAuthoritative AHOS project brief (facts and requirements):\n' + json.dumps(PROJECT_CONTEXT, ensure_ascii=False, indent=2)
