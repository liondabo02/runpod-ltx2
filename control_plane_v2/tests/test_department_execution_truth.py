from ahos.control_center import ControlCenterState, render_dashboard
from ahos.projects import ProjectLink


def test_registered_studio_is_not_production_executor(tmp_path):
    state = ControlCenterState(tmp_path / 'holding')
    state.handle_command('çizgi film departmanı kur')
    rows = {d['department_id']: d for d in state.departments()}
    assert rows['creative']['execution']['state'] == 'not_bound'
    assert not rows['creative']['execution']['production_ready']
    assert rows['guvenlik']['execution']['state'] == 'scanner_bound'
    assert 'Üretim yürütücüsü bağlı değil' in render_dashboard(state.snapshot())


def test_actual_web_binding_is_separate_from_general_readiness(tmp_path):
    state = ControlCenterState(tmp_path / 'holding')
    project = tmp_path / 'web'
    project.mkdir()
    (project / 'index.html').write_text('<html></html>', encoding='utf-8')
    state.console.projects.link(ProjectLink(project_id='web', name='Web', path=project, department_id='software'))
    status = state.department_execution('software')
    assert status['state'] == 'web_executor_bound'
    assert not status['production_ready']
    (project / 'index.html').unlink()
    assert state.department_execution('software')['state'] == 'unsupported_project'
