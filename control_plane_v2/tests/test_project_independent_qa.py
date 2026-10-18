import json
from pathlib import Path
import pytest
from ahos.project_qa import MAX_PROJECT_BYTES, make_project_qa
from ahos.worker_runtime import WorkerExecutionResult
from ahos.workforce_execution import WorkItem


def setup(tmp_path, broken=False):
    root = tmp_path / 'project'
    (root / 'www').mkdir(parents=True)
    (root / 'www/index.html').write_text('<html><script src="app.js"></script></html>', encoding='utf-8')
    if not broken:
        (root / 'www/app.js').write_text('const ready = true;', encoding='utf-8')
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    artifact = evidence / 'worker.md'
    artifact.write_text('Worker claims success', encoding='utf-8')
    item = WorkItem(task_id='work:produce', title='Web üretimi', department='software', required_capabilities=frozenset({'javascript'}))
    result = WorkerExecutionResult(task_id=item.task_id, worker_id='developer', success=True, summary='Everything passed', artifacts=(str(artifact),))
    return root, evidence, item, result


def test_false_worker_success_rejected(tmp_path):
    root, evidence, item, result = setup(tmp_path, broken=True)
    assert not make_project_qa(root, evidence)(item, result, 'reviewer').passed


def test_valid_static_project_has_independent_hash_evidence(tmp_path):
    root, evidence, item, result = setup(tmp_path)
    qa = make_project_qa(root, evidence)(item, result, 'reviewer')
    assert qa.passed
    report = json.loads(next(evidence.glob('qa-*.json')).read_text(encoding='utf-8'))
    assert len(report['source_hashes']) == 2
    assert report['producer'] != report['verifier']
    assert 'functionality' in report['scope']
    assert report['model_calls'] == 0


def test_self_review_rejected(tmp_path):
    root, evidence, item, result = setup(tmp_path)
    assert not make_project_qa(root, evidence)(item, result, 'developer').passed


def test_missing_artifact_rejected(tmp_path):
    root, evidence, item, result = setup(tmp_path)
    Path(result.artifacts[0]).unlink()
    assert not make_project_qa(root, evidence)(item, result, 'reviewer').passed


def test_oversized_project_rejected(tmp_path):
    root, evidence, item, result = setup(tmp_path)
    with (root / 'too-large.bin').open('wb') as f:
        f.truncate(MAX_PROJECT_BYTES + 1)
    assert not make_project_qa(root, evidence)(item, result, 'reviewer').passed


def test_another_tasks_result_rejected(tmp_path):
    root, evidence, item, result = setup(tmp_path)
    other = WorkerExecutionResult(task_id='other', worker_id='developer', success=True, summary='passed', artifacts=result.artifacts)
    assert not make_project_qa(root, evidence)(item, other, 'reviewer').passed


def test_department_save_recovers_transient_file_lock(tmp_path, monkeypatch):
    from ahos.departments import DepartmentBook
    book = DepartmentBook(tmp_path / 'departments.json', seed=True)
    original = Path.replace
    calls = []
    def replace(path, target):
        calls.append(str(path))
        if len(calls) < 3:
            raise PermissionError('transient lock')
        return original(path, target)
    monkeypatch.setattr(Path, 'replace', replace)
    book.save()
    assert len(calls) == 3
    assert not list(tmp_path.glob('*.tmp'))
    assert json.loads((tmp_path / 'departments.json').read_text(encoding='utf-8'))['departments']


def test_department_save_failure_preserves_previous_record(tmp_path, monkeypatch):
    from ahos.departments import DepartmentBook
    book = DepartmentBook(tmp_path / 'departments.json', seed=True)
    before = book.path.read_bytes()
    def locked(path, target):
        raise PermissionError('persistent lock')
    monkeypatch.setattr(Path, 'replace', locked)
    with pytest.raises(PermissionError):
        book.save()
    assert book.path.read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))


def test_owner_console_binds_independent_project_qa(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from ahos.owner_console import build_default_console
    from ahos.mission_orchestrator import MissionStatus
    root, evidence, item, result = setup(tmp_path)
    monkeypatch.delenv('AHOS_EXECUTOR', raising=False)
    console = build_default_console(tmp_path / 'holding')
    monkeypatch.setattr(console, '_project_for_department', lambda ident: SimpleNamespace(path=root, work_path=None))
    outcome = console.run_department_mission(console.book.require('software'), 'Web kalite eksiklerini düzelt')
    assert outcome.mission.status is MissionStatus.COMPLETED
    reports = list(console.artifacts_root.glob('qa-*.json'))
    assert len(reports) == 3
    for path in reports:
        record = json.loads(path.read_text(encoding='utf-8'))
        assert record['passed']
        assert record['producer'] != record['verifier']


def test_hashing_uses_bounded_chunks_not_whole_file(tmp_path, monkeypatch):
    from ahos.project_qa import digest_file, HASH_CHUNK_BYTES
    import hashlib
    path = tmp_path / 'large.dat'
    content = b'x' * (HASH_CHUNK_BYTES * 3 + 7)
    path.write_bytes(content)
    def forbidden(*args, **kwargs):
        raise AssertionError('whole-file read forbidden')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    digest, count = digest_file(path, len(content))
    assert digest == hashlib.sha256(content).hexdigest()
    assert count == len(content)
    with pytest.raises(ValueError):
        digest_file(path, len(content) - 1)
