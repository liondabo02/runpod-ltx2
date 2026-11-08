"""Acceptance gates for the isolated hardening candidate, not live services."""
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('holding_probe', Path(__file__).with_name('holding_behavior_acceptance.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_goal_requires_real_production_and_survives_restart(tmp_path):
    result = probe.run(tmp_path / 'run')
    assert result['department_created'] and result['department_persisted']
    assert result['story_mission_status'] == 'MissionStatus.BLOCKED'
    assert not result['missing_asset_accepted']
    assert not result['no_verifier_accepted']
    assert not result['model_supplied_command_executed']
    assert not result['model_command_accepted']
    assert result['external_calls'] == 0


def test_real_web_hygiene_changes_files_and_missing_asset_blocks(tmp_path):
    from ahos.code_work import make_project_executor
    from ahos.workforce_execution import WorkItem
    root = tmp_path / 'project'
    (root / 'www').mkdir(parents=True)
    index = root / 'www/index.html'
    index.write_text('<html><head></head><body><script src="missing.js"></script></body></html>', encoding='utf-8')
    item = WorkItem(task_id='real:produce', title='Web kalite eksiklerini düzelt', department='software', required_capabilities=frozenset({'javascript'}))
    execute = make_project_executor(root, tmp_path / 'evidence')
    before = index.read_text(encoding='utf-8')
    first = execute(item, 'worker')
    assert index.read_text(encoding='utf-8') != before
    assert not first.success
    (root / 'www/missing.js').write_text('const valid = true;', encoding='utf-8')
    assert execute(item, 'worker').success
