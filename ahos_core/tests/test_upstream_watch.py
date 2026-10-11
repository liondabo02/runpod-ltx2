import json
from ahos.upstream_watch import watch_upstream


def catalog(tmp_path):
    repo = tmp_path / 'repo'
    docs = repo / 'ahos_core/docs'
    docs.mkdir(parents=True)
    (docs / 'holding-upstream-candidates.json').write_text(json.dumps({
        'repositories': [{'full_name': 'owner/tool'}]}))
    return repo


def test_disabled_watcher_never_fetches(tmp_path):
    assert watch_upstream(tmp_path, tmp_path, fetch=lambda _: 1)['status'] == 'external_disabled'


def test_daily_baseline_then_change_queues_review_once(tmp_path):
    repo = catalog(tmp_path)
    runtime = tmp_path / 'runtime'
    calls = []
    def fetch(name):
        calls.append(name)
        return {'pushed_at': str(len(calls)), 'license_spdx': 'MIT'}
    first = watch_upstream(runtime, repo, allow_external=True, fetch=fetch, now=100)
    assert first['review_tasks'] == []
    assert first['installed'] is False
    watch_upstream(runtime, repo, allow_external=True, fetch=fetch, now=101)
    assert len(calls) == 1
    second = watch_upstream(runtime, repo, allow_external=True, fetch=fetch, now=86501)
    assert len(second['review_tasks']) == 1
    from ahos.department_runtime import DepartmentRuntime
    tasks = DepartmentRuntime(runtime / 'departments').snapshot()['tasks']
    assert tasks[0]['status'] == 'queued'
    assert tasks[0]['department'] == 'research'


def test_error_is_bounded_and_retry_delayed(tmp_path):
    repo = catalog(tmp_path)
    def fetch(name):
        raise RuntimeError('secret-token-do-not-persist')
    result = watch_upstream(tmp_path / 'runtime', repo, allow_external=True, fetch=fetch, now=10)
    assert result['next_check_at'] == 3610
    assert 'secret-token' not in json.dumps(result)
    assert result['errors'][0]['error_type'] == 'RuntimeError'
