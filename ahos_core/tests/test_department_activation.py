import json
import pytest
from ahos.department_activation import activate_departments
from ahos.department_runtime import DepartmentRuntime
from ahos.control_center import ControlCenterState, render_dashboard


def test_activation_preserves_coding_and_is_idempotent(tmp_path):
    config = tmp_path / 'company-service-config.json'
    coding = {'enabled': True, 'builder_command': ['python', '-m', 'builder']}
    config.write_text(json.dumps({'coding_supervisor': coding}))
    activate_departments(tmp_path, allow_external=True)
    activate_departments(tmp_path, allow_external=True)
    assert json.loads(config.read_text())['coding_supervisor'] == coding
    snapshot = DepartmentRuntime(tmp_path / 'departments').snapshot()
    assert len(snapshot['tasks']) == 11
    assert all(task['status'] == 'queued' for task in snapshot['tasks'])
    assert not snapshot['publishing_enabled']


def test_activation_requires_external_authorization(tmp_path):
    with pytest.raises(ValueError, match='allow-external'):
        activate_departments(tmp_path, allow_external=False)
    assert not (tmp_path / 'company-service-config.json').exists()


def test_panel_reviews_draft_without_publishing(tmp_path):
    state = ControlCenterState(tmp_path)
    state.create_department_task('Prepare the support runbook', 'support')
    runtime = DepartmentRuntime(tmp_path / 'departments', lambda _: json.dumps({
        'title': 'Runbook', 'content': 'Diagnose provider outages using recorded task status and retry only after configuration has been checked.',
        'assumptions': [], 'acceptance_checks': ['Check status without exposing credentials'],
    }))
    task = runtime.run_once()['tasks'][0]
    assert state.department_review(task['task_id'])['artifact']['execution_performed'] is False
    page = render_dashboard(state.snapshot())
    assert 'Department Work' in page and 'Review draft' in page
    state.decide_department_task(task['task_id'], True, task['artifact_hash'])
    assert runtime.snapshot()['tasks'][0]['status'] == 'owner_approved'
    assert not runtime.snapshot()['publishing_enabled']


def test_panel_does_not_treat_old_department_status_as_live(tmp_path):
    (tmp_path / 'department-service-status.json').write_text(json.dumps({
        'status': 'polled', 'timestamp': '2000-01-01T00:00:00+00:00', 'pid': 1,
    }))
    assert ControlCenterState(tmp_path).snapshot()['departments']['service']['status'] == 'stale'
