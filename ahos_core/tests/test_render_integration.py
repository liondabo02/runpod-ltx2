import json
import threading
from types import SimpleNamespace
from urllib.request import urlopen
from urllib.error import HTTPError
import pytest
from ahos import render_task
from ahos.queue_drain import drain
from ahos.autonomous_company import PersistentMissionQueue
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.office_server import serve

def test_render_queue_route(tmp_path, monkeypatch):
    path=tmp_path/'workflow.json'; path.write_text('{"1":{"prompt":"{{prompt}}"}}')
    monkeypatch.setenv('AHOS_RENDER_WORKFLOW', str(path))
    monkeypatch.setenv('AHOS_RENDER_OUT', str(tmp_path/'renders'))
    calls=[]
    def fake_render(w, out):
        calls.append(w); out.mkdir(); image=out/'frame.png'; image.write_bytes(b'png'); return [image]
    monkeypatch.setattr(render_task, 'render', lambda w,out: fake_render(w, __import__('pathlib').Path(out)))
    queue=PersistentMissionQueue(tmp_path/'company-service.db')
    queue.enqueue(mission_id='render-test', objective='render: ormanda minipula', primary_department='creative')
    results=[]
    def execute(spec, objective, mission_id, executor=None):
        assert executor is not None
        for task_id in ('a','b'):
            results.append(executor(SimpleNamespace(task_id=task_id, title='planner text'), 'artist'))
        return MissionResult(mission_id, objective, None, MissionStatus.BLOCKED, (), 'independent QA not exercised')
    console=SimpleNamespace(runtime_dir=tmp_path, queue=queue,
        book=SimpleNamespace(get=lambda x: SimpleNamespace(department_id=x)),
        _execute=execute, _record=lambda mid, owner, result: queue.block(mid,owner=owner,result=result))
    drain(console,limit=1)
    assert len(calls)==1 and calls[0]['1']['prompt']=='ormanda minipula'
    assert all(r.success for r in results)
    assert [r.task_id for r in results]==['a','b']

def test_office_routes_and_containment(tmp_path):
    runtime=tmp_path/'runtime'; renders=runtime/'artifacts'/'renders'; renders.mkdir(parents=True)
    config=tmp_path/'config'; config.mkdir()
    roster={'oyun-manager':{'name':'Ada Deniz','title':'Müdür','department':'oyun'}}
    (config/'roster.json').write_text(json.dumps(roster))
    for n in range(12): (renders/f'{n}.png').write_bytes(b'PNG')
    (tmp_path/'secret.png').write_bytes(b'SECRET')
    server=serve(runtime,port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/ofis3d') as r:
            assert r.status==200 and 'ÜRETİMLER' in r.read().decode()
        with urlopen(base+'/api/roster') as r: assert json.load(r)==roster
        with urlopen(base+'/api/talk?worker=oyun-manager&msg=neden') as r: assert json.load(r)['reply']
        with urlopen(base+'/api/renders') as r:
            files=json.load(r);assert len(files)==10 and all(f['size']==3 for f in files)
        with urlopen(base+'/renders/0.png') as r: assert r.read()==b'PNG'
        for path in ('/renders/..%2Fsecret.png','/renders/..%5Csecret.png','/renders/a.txt','/renders/missing.png'):
            with pytest.raises(HTTPError) as exc: urlopen(base+path)
            assert exc.value.code==404
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
