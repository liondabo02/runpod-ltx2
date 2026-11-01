from ahos.project_qa import make_project_qa
from ahos.worker_runtime import WorkerExecutionResult
from ahos.workforce_execution import WorkItem
import pytest

@pytest.mark.parametrize('record',[None,'{broken'])
def test_untrusted_gate_is_blocked_before_host_execution(tmp_path, monkeypatch, record):
    root=tmp_path/'project'
    (root/'www').mkdir(parents=True)
    (root/'www/index.html').write_text('<html><body>test</body></html>')
    (root/'tools').mkdir()
    (root/'tools/check_offline.py').write_text('# never execute this unreviewed gate')
    evidence=tmp_path/'evidence'; evidence.mkdir()
    artifact=evidence/'output.md'; artifact.write_text('candidate output')
    if record is not None:
        (evidence/'acceptance-baseline.json').write_text(record)
    calls=[]
    def forbidden(*a,**kw):
        calls.append(a)
        raise AssertionError('untrusted gate reached host execution')
    monkeypatch.setattr('ahos.project_qa.subprocess.run',forbidden)
    item=WorkItem(task_id='job:produce',title='feature',department='software',required_capabilities=frozenset({'python'}))
    result=WorkerExecutionResult(task_id=item.task_id,worker_id='producer',success=True,summary='candidate',artifacts=(str(artifact),))
    decision=make_project_qa(root,evidence)(item,result,'independent-qa')
    assert not decision.passed
    assert not calls
    assert 'Kabul testi' in decision.summary
