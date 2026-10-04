"""Daily metadata checks for a reviewed GitHub catalog; never installs code."""
from __future__ import annotations

import json
import re
import time
import urllib.request
import uuid
from pathlib import Path

_REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def _fetch(full_name: str) -> dict:
    request = urllib.request.Request(
        'https://api.github.com/repos/' + full_name,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'AHOS-upstream-watch'},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read(512_001)
    if len(body) > 512_000:
        raise ValueError('upstream response exceeds limit')
    result = json.loads(body)
    if not isinstance(result, dict) or result.get('full_name', '').lower() != full_name.lower():
        raise ValueError('unexpected repository identity')
    # Only typed metadata is retained, not README instructions or descriptions.
    license_data = result.get('license') or {}
    return {
        'pushed_at': result.get('pushed_at'),
        'default_branch': result.get('default_branch'),
        'license_spdx': license_data.get('spdx_id') if isinstance(license_data, dict) else None,
        'archived': result.get('archived') is True,
    }


def watch_upstream(runtime_dir: Path, repository: Path, *, allow_external: bool = False,
                   fetch=None, now: float | None = None) -> dict:
    root, repo = Path(runtime_dir), Path(repository)
    clock = time.time() if now is None else now
    path = root / 'holding-upstream-watch.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not allow_external:
        return {'status': 'external_disabled'}
    if float(previous.get('next_check_at', 0)) > clock:
        return previous
    catalog = json.loads((repo / 'ahos_core/docs/holding-upstream-candidates.json').read_text(encoding='utf-8'))
    entries = catalog.get('repositories', [])
    if not isinstance(entries, list) or len(entries) > 12:
        raise ValueError('invalid reviewed catalog')
    records, changes, errors = {}, [], []
    old = previous.get('repositories', {})
    reader = fetch or _fetch
    for item in entries:
        name = item['full_name']
        if not _REPO.fullmatch(name):
            raise ValueError('invalid repository name')
        try:
            current = reader(name)
            if not isinstance(current, dict):
                raise ValueError('invalid upstream metadata')
            if name in old and current != old[name]:
                changes.append(name)
            records[name] = current
        except Exception as exc:
            errors.append({'repository': name, 'error_type': type(exc).__name__})
            if name in old:
                records[name] = old[name]
    # Failed scans retry after one hour, successful ones daily. No paid providers.
    result = {'schema': 'ahos.holding-upstream-watch.v1',
              'status': 'partial' if errors else 'checked', 'checked_at': clock,
              'next_check_at': clock + (3600 if errors else 86400),
              'repositories': records, 'changed_repositories': changes,
              'errors': errors, 'installed': False, 'review_tasks': []}
    if changes:
        from .department_runtime import DepartmentRuntime, DepartmentTask
        import hashlib
        queue = DepartmentRuntime(root / 'departments')
        for name in changes:
            fingerprint = hashlib.sha256(json.dumps(records[name], sort_keys=True).encode()).hexdigest()[:16]
            task_id = 'UPSTREAM-' + name.replace('/', '-') + '-' + fingerprint
            queue.enqueue(DepartmentTask(task_id, 'research',
                f'Review upstream change in https://github.com/{name}. Metadata evidence: '
                + json.dumps(records[name], sort_keys=True)
                + '. Verify license, exact commit, Windows support, AHOS compatibility and tests. '
                  'Produce a concrete integration proposal. Metadata alone does not prove a useful update; '
                  'do not install code, claim deployment, or weaken owner approvals.'))
            result['review_tasks'].append(task_id)
    root.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(result, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return result
