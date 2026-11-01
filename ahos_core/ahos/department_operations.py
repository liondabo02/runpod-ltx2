"""Read-only operating contracts for existing departments; never spawn agents.

Configuration readiness is distinct from demonstrated production capability.
Departments without their own QA use an existing independent quality worker.
"""
from __future__ import annotations

from collections import Counter


def operating_contracts(departments: list[dict]) -> dict[str, dict]:
    workers = [w for d in departments for w in d.get('workers', []) if isinstance(w, dict)]
    duplicate_ids = {key for key, count in Counter(w.get('worker_id') for w in workers).items() if count > 1}
    shared_qa = next((w for d in departments if d.get('department_id') == 'quality'
                      for w in d.get('workers', []) if w.get('role') == 'qa_engineer'), None)
    holding_manager = next((w.get('worker_id') for d in departments if d.get('department_id') == 'holding'
                            for w in d.get('workers', []) if w.get('role') == 'department_manager'), None)
    result = {}
    for department in departments:
        ident = str(department.get('department_id') or '')
        local = [w for w in department.get('workers', []) if isinstance(w, dict)]
        by_id = {w.get('worker_id'): w for w in local}
        managers = [w for w in local if w.get('role') == 'department_manager']
        builders = [w for w in local if w.get('role') not in {'department_manager', 'qa_engineer'}]
        local_qa = [w for w in local if w.get('role') == 'qa_engineer']
        manager = managers[0].get('worker_id') if len(managers) == 1 else None
        qa = (local_qa[0] if local_qa else shared_qa)
        issues = []
        if not ident: issues.append('Departman kimliği eksik')
        if len(managers) != 1: issues.append('Tam olarak bir departman yöneticisi gerekli')
        if not builders and not local_qa: issues.append('Uygulayıcı işçi eksik')
        if not qa: issues.append('Bağımsız QA sorumlusu eksik')
        if any(w.get('worker_id') in duplicate_ids for w in local): issues.append('İşçi kimliği departmanlar arasında çakışıyor')
        for worker in local:
            if worker.get('role') == 'department_manager': continue
            seen = set(); current = worker
            while current.get('reports_to'):
                parent = current['reports_to']
                if parent in seen or parent == worker.get('worker_id'):
                    issues.append('Raporlama zincirinde döngü'); break
                seen.add(parent)
                if parent not in by_id:
                    issues.append('Raporlama zincirinde bulunamayan üst işçi'); break
                current = by_id[parent]
            if current.get('worker_id') != manager and 'Raporlama zincirinde döngü' not in issues:
                issues.append('İşçi yöneticiye bağlı değil')
        result[ident] = {
            'department_id': ident, 'status': 'needs_attention' if issues else 'configured',
            'manager': manager, 'execution_workers': [w.get('worker_id') for w in builders],
            'qa_worker': qa.get('worker_id') if qa else None,
            'qa_mode': 'local' if local_qa else 'shared_quality',
            'escalation_manager': holding_manager,
            'workflow': ['brief', 'discovery', 'plan', 'implementation', 'independent_qa', 'delivery'],
            'delivery_requires': ['artifact', 'acceptance_result', 'remaining_risks'],
            'configuration_only': True, 'production_verified': False,
            'issues': sorted(set(issues)),
        }
    return result
