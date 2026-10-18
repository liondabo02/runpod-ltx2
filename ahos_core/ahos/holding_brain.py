"""Persistent holding observations and scoped self-improvement handoffs.

This coordinator observes local evidence. It does not pretend to be a model,
execute its proposed edits, approve them, discover the Internet, or control a PC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

from .coding_supervisor import CodingSupervisorStore, CodingTaskStatus
from .coding_worker import CodingBacklogItem
from .department_context import PROJECT_CONTEXT
from .department_runtime import DepartmentRuntime
from .verification_baseline import load_verification_baseline

_REPAIRS = {
    'coding_exhausted': {
        'revision': 2,
        'title': 'AHOS coding reliability: diagnose failed builder responses and repair code production',
        'instruction': 'Inspect the persisted failing task evidence and builder response diagnostics locally. Repair the actual root cause. Preserve original task requirements, existing public APIs, owner controls and all tests. Do not claim a coding task succeeded without an actual scoped patch and passing checks. Never include credentials or raw provider payloads in owner-facing reports.',
        'paths': ('ahos_core/ahos/coding_supervisor.py', 'ahos_core/ahos/coding_worker.py', 'ahos_core/ahos/openrouter_coding_builder.py', 'ahos_core/ahos/ollama_coding_builder.py', 'ahos_core/tests/test_ollama_coding_builder.py', 'ahos_core/tests/test_openrouter_coding_builder.py', 'ahos_core/tests/test_coding_supervisor.py', 'ahos_core/tests/test_coding_worker.py'),
        'tests': ('ahos_core/tests/test_ollama_coding_builder.py', 'ahos_core/tests/test_openrouter_coding_builder.py', 'ahos_core/tests/test_coding_supervisor.py', 'ahos_core/tests/test_coding_worker.py'),
    },
    'department_exhausted': {
        'title': 'AHOS department reliability: diagnose exhausted draft production failures',
        'instruction': 'Inspect failed department evidence locally and repair the actual provider or validation cause. Distinguish rate limits, authentication, network and malformed output. Respect Retry-After and free-provider restrictions. Do not bypass cost controls, fabricate draft success or weaken draft validation.',
        'paths': ('ahos_core/ahos/department_provider.py', 'ahos_core/ahos/department_runtime.py', 'ahos_core/tests/test_department_provider.py', 'ahos_core/tests/test_department_runtime.py'),
        'tests': ('ahos_core/tests/test_department_provider.py', 'ahos_core/tests/test_department_runtime.py'),
    },
}


def _safe_id(value: str) -> str:
    # Queue IDs may be owner supplied: persist a stable digest, not arbitrary text.
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


class HoldingBrain:
    def __init__(self, runtime_dir: str | Path, repository: str | Path,
                 *, python_executable: str = sys.executable) -> None:
        self.root = Path(runtime_dir).resolve()
        self.repository = Path(repository).resolve()
        self.python = str(python_executable)
        self.root.mkdir(parents=True, exist_ok=True)

    def observe(self) -> dict:
        gaps = []
        baseline, baseline_status = load_verification_baseline(
            self.root / 'verification-baseline.json'
        )
        coding = CodingSupervisorStore(self.root / 'coding-supervisor-queue.json').all()
        # Do not allow the brain's own failed repair tasks to spawn further repairs.
        exhausted_all = [t for t in coding if t.status is CodingTaskStatus.RETRIES_EXHAUSTED
                         and not t.task_id.startswith('BRAIN-')]
        exhausted = [
            t for t in exhausted_all
            if baseline is None or not baseline.covers('coding_reliability', t.updated_at)
        ]
        historical_coding = [t for t in exhausted_all if t not in exhausted]
        if exhausted:
            gaps.append({'kind': 'coding_exhausted', 'count': len(exhausted),
                         'source_ids': [_safe_id(t.task_id) for t in exhausted],
                         'recommendation': 'Kodlama işçisinin gerçek başarısızlık nedenini inceleyip testli düzeltme hazırlayın.'})
        department = DepartmentRuntime(self.root / 'departments').snapshot()
        failed_all = [t for t in department['tasks'] if t['status'] == 'retries_exhausted']
        failed = [
            t for t in failed_all
            if baseline is None or not baseline.covers('department_runtime', str(t.get('updated_at') or ''))
        ]
        historical_department = [t for t in failed_all if t not in failed]
        if failed:
            gaps.append({'kind': 'department_exhausted', 'count': len(failed),
                         'source_ids': [_safe_id(t['task_id']) for t in failed],
                         'recommendation': 'Departman hatalarının nedenini kanıttan belirleyin; aynı isteği körlemesine tekrarlamayın.'})
        waiting = department['counts'].get('waiting_provider', 0) + sum(
            t.status is CodingTaskStatus.WAITING_PROVIDER for t in coding)
        if waiting:
            gaps.append({'kind': 'provider_cooldown', 'count': waiting,
                         'recommendation': 'Sağlayıcının bekleme süresini koruyun; ücretli modele kendiliğinden geçmeyin.'})
        requirements = [{'id': key, 'requirement': text, 'verification': 'not_audited'}
                        for key, text in PROJECT_CONTEXT['requirements'].items()]
        baseline_summary = {
            'status': baseline_status,
            'commit_sha': baseline.commit_sha if baseline is not None else '',
            'platform': baseline.platform if baseline is not None else '',
            'verified_at': baseline.verified_at.isoformat() if baseline is not None else None,
            'proofs': sorted(baseline.proofs) if baseline is not None else [],
        }
        historical_failures = {
            'coding_exhausted': {
                'count': len(historical_coding),
                'source_ids': [_safe_id(t.task_id) for t in historical_coding],
            },
            'department_exhausted': {
                'count': len(historical_department),
                'source_ids': [_safe_id(t['task_id']) for t in historical_department],
            },
        }
        return {'schema': 'ahos.holding-brain.v1',
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'gaps': gaps, 'requirements': requirements,
                'verification_baseline': baseline_summary,
                'historical_failures': historical_failures,
                'capability': 'local_evidence_coordination',
                'production_ready': False,
                'readiness_note': 'Queue observation is not a complete holding or film acceptance audit.',
                'external_research_enabled': False, 'pc_control_enabled': False,
                'owner_approval_required': True}

    def cycle(self, *, dispatch: bool = False) -> dict:
        snapshot = self.observe()
        handoffs = []
        store = CodingSupervisorStore(self.root / 'coding-supervisor-queue.json')
        for gap in snapshot['gaps']:
            kind = gap['kind']
            if kind not in _REPAIRS:
                continue
            revision = _REPAIRS[kind].get('revision', 1)
            task_id = 'BRAIN-' + kind.replace('_', '-').upper() + f'-V{revision}'
            prior = store.get(task_id)
            if prior is not None:
                handoffs.append({'gap': kind, 'task_id': task_id, 'status': prior.status.value})
                continue
            if not dispatch:
                handoffs.append({'gap': kind, 'task_id': task_id, 'status': 'proposed'})
                continue
            spec = _REPAIRS[kind]
            # Missing scope files mean the known repair contract cannot be executed.
            if not all((self.repository / path).is_file() for path in spec['paths']):
                handoffs.append({'gap': kind, 'task_id': task_id, 'status': 'blocked_missing_scope'})
                continue
            item = CodingBacklogItem(
                task_id=task_id, title=spec['title'] + '\n\n' + spec['instruction'],
                repository=self.repository, base_ref='HEAD', allowed_paths=spec['paths'],
                test_commands=((self.python, '-m', 'pytest', '-q', *spec['tests']),))
            record = store.enqueue(item, idempotency_key=task_id, max_attempts=2, priority=10)
            handoffs.append({'gap': kind, 'task_id': task_id, 'status': record.status.value})
        snapshot['handoffs'] = handoffs
        snapshot['automatic_dispatch_enabled'] = dispatch
        target = self.root / 'holding-brain.json'
        history = []
        if target.exists():
            try:
                previous = json.loads(target.read_text(encoding='utf-8'))
                for entry in previous.get('decision_history', [])[-49:]:
                    # Reconstruct controlled values rather than recopying arbitrary state.
                    if entry.get('gap') in _REPAIRS and entry.get('decision') in {'proposed', 'queued', 'blocked_missing_scope'}:
                        history.append({key: entry[key] for key in ('gap', 'decision')})
            except (ValueError, OSError, TypeError, AttributeError, KeyError):
                history = []
        for handoff in handoffs:
            entry = {'gap': handoff['gap'], 'decision': handoff['status']}
            if handoff['status'] in {'proposed', 'queued', 'blocked_missing_scope'} and (not history or history[-1] != entry):
                history.append(entry)
        snapshot['decision_history'] = history[-50:]
        temp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return snapshot


def run_brain_cycle(runtime_dir: str | Path, repository: str | Path, *,
                    dispatch: bool = False, python_executable: str = sys.executable) -> dict:
    return HoldingBrain(runtime_dir, repository, python_executable=python_executable).cycle(dispatch=dispatch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--dispatch', action='store_true', help='Enqueue scoped repair proposals; owner gates remain intact')
    args = parser.parse_args()
    # Console pipes on Windows may use cp1252; JSON escapes preserve all text.
    print(json.dumps(run_brain_cycle(args.runtime_dir, args.repository, dispatch=args.dispatch), ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
