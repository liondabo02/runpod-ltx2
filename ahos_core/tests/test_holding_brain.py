from pathlib import Path
import json

from ahos.coding_supervisor import CodingSupervisorStore
from ahos.coding_worker import CodingBacklogItem
from ahos.holding_brain import HoldingBrain, _REPAIRS


def fail_task(root, repo, task_id='OWNER-TASK'):
    store = CodingSupervisorStore(root / 'coding-supervisor-queue.json')
    store.enqueue(CodingBacklogItem(task_id, 'original scope', repo, allowed_paths=('src',)), max_attempts=1)
    store.claim('test')
    store.finish(task_id, 'test', success=False, reason='secret-key-test-value')
    return store


def test_brain_observes_without_dispatch_or_secret_copy(tmp_path):
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    root.mkdir()
    store = fail_task(root, repo)
    result = HoldingBrain(root, repo).cycle()
    assert len(store.all()) == 1
    assert result['handoffs'][0]['status'] == 'proposed'
    assert result['gaps'][0]['count'] == 1
    assert result['owner_approval_required'] is True
    assert result['production_ready'] is False
    assert 'secret-key-test-value' not in (root / 'holding-brain.json').read_text()
    assert all(item['verification'] == 'not_audited' for item in result['requirements'])


def test_dispatch_dedupes_and_does_not_recursive_repair(tmp_path):
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    root.mkdir()
    for path in _REPAIRS['coding_exhausted']['paths']:
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('')
    store = fail_task(root, repo)
    brain = HoldingBrain(root, repo)
    first = brain.cycle(dispatch=True)
    task_id = first['handoffs'][0]['task_id']
    brain.cycle(dispatch=True)
    assert len(store.all()) == 2
    repair = store.get(task_id)
    assert repair.allowed_paths == _REPAIRS['coding_exhausted']['paths']
    assert repair.test_commands[0][1:4] == ('-m', 'pytest', '-q')
    for _ in range(2):
        store.claim('repair')
        store.finish(task_id, 'repair', success=False, reason='failed')
    result = brain.cycle(dispatch=True)
    assert len(store.all()) == 2
    assert result['gaps'][0]['count'] == 1
    assert result['handoffs'][0]['status'] == 'retries_exhausted'


def test_missing_scope_blocks_and_corrupted_history_is_replaced(tmp_path):
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    root.mkdir()
    store = fail_task(root, repo)
    (root / 'holding-brain.json').write_text('{broken')
    result = HoldingBrain(root, repo).cycle(dispatch=True)
    assert result['handoffs'][0]['status'] == 'blocked_missing_scope'
    assert len(store.all()) == 1
    assert len(result['decision_history']) <= 50
    json.loads((root / 'holding-brain.json').read_text())


def test_department_failure_and_cooldown_are_distinct(tmp_path):
    from ahos.department_runtime import DepartmentRuntime, DepartmentTask
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    runtime = DepartmentRuntime(root / 'departments')
    runtime.enqueue(DepartmentTask('DRAFT-1', 'research', 'research requirements'))
    with runtime._lock():
        data = runtime._load()
        data['tasks']['DRAFT-1'].update(status='waiting_provider', retry_at=9999999999)
        data['provider_retry_at'] = 9999999999
        runtime._save(data)
    result = HoldingBrain(root, repo).cycle(dispatch=True)
    assert result['gaps'][0]['kind'] == 'provider_cooldown'
    assert result['handoffs'] == []
    with runtime._lock():
        data = runtime._load()
        data['tasks']['DRAFT-1'].update(status='retries_exhausted')
        runtime._save(data)
    result = HoldingBrain(root, repo).cycle()
    assert result['gaps'][0]['kind'] == 'department_exhausted'
    assert result['handoffs'][0]['status'] == 'proposed'


def test_decision_history_stays_bounded_and_omits_uncontrolled_fields(tmp_path):
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    root.mkdir()
    fail_task(root, repo)
    (root / 'holding-brain.json').write_text(json.dumps({'decision_history': [
        {'gap': 'coding_exhausted', 'decision': 'queued', 'secret': 'never-copy'}
        for _ in range(100)]}))
    result = HoldingBrain(root, repo).cycle()
    assert len(result['decision_history']) == 50
    assert 'never-copy' not in (root / 'holding-brain.json').read_text()


def test_coding_repair_can_modify_and_test_local_ollama_adapter(tmp_path):
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    root.mkdir()
    for path in _REPAIRS['coding_exhausted']['paths']:
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('')
    store = fail_task(root, repo)
    result = HoldingBrain(root, repo).cycle(dispatch=True)
    repair = store.get(result['handoffs'][0]['task_id'])
    assert 'ahos_core/ahos/ollama_coding_builder.py' in repair.allowed_paths
    assert 'ahos_core/tests/test_ollama_coding_builder.py' in repair.allowed_paths
    assert 'ahos_core/tests/test_ollama_coding_builder.py' in repair.test_commands[0]
    assert 'ahos_core/ahos/openrouter_coding_builder.py' in repair.allowed_paths
    assert repair.max_attempts == 2
    assert result['owner_approval_required'] is True
    assert store.get('OWNER-TASK').allowed_paths == ('src',)


def test_revised_coding_contract_preserves_exhausted_v1_and_dedupes_v2(tmp_path):
    root, repo = tmp_path / 'runtime', tmp_path / 'repo'
    root.mkdir()
    for path in _REPAIRS['coding_exhausted']['paths']:
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('')
    store = fail_task(root, repo)
    old_id = 'BRAIN-CODING-EXHAUSTED-V1'
    store.enqueue(CodingBacklogItem(old_id, 'old repair contract', repo,
                                   allowed_paths=('ahos_core/ahos/openrouter_coding_builder.py',)),
                  max_attempts=1)
    store.claim('old-worker')
    old_record = store.finish(old_id, 'old-worker', success=False, reason='old failure')
    brain = HoldingBrain(root, repo)
    first = brain.cycle(dispatch=True)
    assert first['handoffs'][0]['task_id'] == 'BRAIN-CODING-EXHAUSTED-V2'
    assert first['handoffs'][0]['status'] == 'queued'
    assert store.get(old_id) == old_record
    brain.cycle(dispatch=True)
    assert len(store.all()) == 3
    new_id = first['handoffs'][0]['task_id']
    for _ in range(2):
        store.claim('new-worker')
        store.finish(new_id, 'new-worker', success=False, reason='bounded failure')
    final = brain.cycle(dispatch=True)
    assert final['handoffs'][0]['status'] == 'retries_exhausted'
    assert len(store.all()) == 3
    assert store.get(old_id) == old_record



def _write_baseline(root, *, coding=True, department=True, verified_at="2099-01-01T00:00:00Z"):
    (root / "verification-baseline.json").write_text(json.dumps({
        "schema": "ahos.verification-baseline.v1",
        "verified_at": verified_at,
        "commit_sha": "verified-commit",
        "platform": "windows",
        "proofs": {
            "coding_reliability": coding,
            "department_runtime": department,
        },
    }), encoding="utf-8")


def test_verified_baseline_moves_old_coding_failure_to_history(tmp_path):
    root, repo = tmp_path / "runtime", tmp_path / "repo"
    root.mkdir()
    fail_task(root, repo)
    _write_baseline(root, coding=True, department=False)
    result = HoldingBrain(root, repo).cycle()
    assert not any(gap["kind"] == "coding_exhausted" for gap in result["gaps"])
    assert result["historical_failures"]["coding_exhausted"]["count"] == 1
    assert result["verification_baseline"]["status"] == "valid"
    assert result["verification_baseline"]["proofs"] == ["coding_reliability"]
    assert result["handoffs"] == []


def test_baseline_without_proof_does_not_hide_coding_failure(tmp_path):
    root, repo = tmp_path / "runtime", tmp_path / "repo"
    root.mkdir()
    fail_task(root, repo)
    _write_baseline(root, coding=False, department=False)
    result = HoldingBrain(root, repo).cycle()
    assert result["gaps"][0]["kind"] == "coding_exhausted"
    assert result["historical_failures"]["coding_exhausted"]["count"] == 0


def test_failure_newer_than_baseline_remains_active(tmp_path):
    root, repo = tmp_path / "runtime", tmp_path / "repo"
    root.mkdir()
    _write_baseline(root, coding=True, verified_at="2020-01-01T00:00:00Z")
    fail_task(root, repo)
    result = HoldingBrain(root, repo).cycle()
    assert result["gaps"][0]["kind"] == "coding_exhausted"
    assert result["historical_failures"]["coding_exhausted"]["count"] == 0


def test_verified_department_failures_become_history_not_repair_handoffs(tmp_path):
    from ahos.department_runtime import DepartmentRuntime, DepartmentTask
    root, repo = tmp_path / "runtime", tmp_path / "repo"
    root.mkdir()
    runtime = DepartmentRuntime(root / "departments")
    runtime.enqueue(DepartmentTask("DRAFT-OLD", "research", "old provider failure"))
    with runtime._lock():
        data = runtime._load()
        data["tasks"]["DRAFT-OLD"].update(
            status="retries_exhausted",
            updated_at="2026-10-01T00:00:00+00:00",
        )
        runtime._save(data)
    _write_baseline(root, coding=False, department=True)
    result = HoldingBrain(root, repo).cycle()
    assert not any(gap["kind"] == "department_exhausted" for gap in result["gaps"])
    assert result["historical_failures"]["department_exhausted"]["count"] == 1
    assert result["handoffs"] == []


def test_corrupted_baseline_fails_closed_and_preserves_gap(tmp_path):
    root, repo = tmp_path / "runtime", tmp_path / "repo"
    root.mkdir()
    fail_task(root, repo)
    (root / "verification-baseline.json").write_text("{broken", encoding="utf-8")
    result = HoldingBrain(root, repo).cycle()
    assert result["verification_baseline"]["status"] == "invalid"
    assert result["gaps"][0]["kind"] == "coding_exhausted"



def test_platform_readiness_is_separate_from_department_acceptance(tmp_path):
    root, repo = tmp_path / "runtime", tmp_path / "repo"
    root.mkdir()
    (root / "verification-baseline.json").write_text(json.dumps({
        "schema": "ahos.verification-baseline.v1",
        "verified_at": "2099-01-01T00:00:00Z",
        "commit_sha": "platform-proof",
        "platform": "windows",
        "proofs": {
            "holding_platform": True,
            "coding_reliability": True,
            "runtime_health": True,
            "recovery": True,
            "owner_gates": True,
            "evidence": True,
        },
    }), encoding="utf-8")
    result = HoldingBrain(root, repo).cycle()
    assert result["gaps"] == []
    assert result["platform_ready"] is True
    assert result["department_acceptance_ready"] is False
    assert result["production_ready"] is False
    status = {item["id"]: item["verification"] for item in result["requirements"]}
    assert status["HOLDING"] == "proven"
    assert status["CODING"] == "proven"
    assert status["RELIABILITY"] == "proven"
    assert status["OWNER_GATES"] == "proven"
    assert status["EVIDENCE"] == "proven"
    assert status["STUDIO"] == "not_proven"
