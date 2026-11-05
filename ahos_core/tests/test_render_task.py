import json
from types import SimpleNamespace
from ahos import render_task

def test_success_and_prompt_escaping(tmp_path, monkeypatch):
    workflow = tmp_path / 'workflow.json'
    workflow.write_text(json.dumps({'1': {'text': '{{prompt}}', 'seed': '{{seed}}'}}))
    output = tmp_path / 'frame.png'
    output.write_bytes(b'image')
    seen = []
    def fake_render(graph, out):
        seen.append(graph)
        return [output]
    monkeypatch.setattr(render_task, 'render', fake_render)
    prompt = 'render: ' + '"orman"\n' * 100
    result = render_task.make_render_executor(workflow, tmp_path)(SimpleNamespace(task_id='t', objective=prompt), 'artist')
    assert result.success and result.artifacts == (str(output),)
    assert result.summary == '1 dosya üretildi'
    assert seen[0]['1']['text'] == prompt.removeprefix('render:').strip()[:400]
    assert seen[0]['1']['seed'] == 0

def test_unavailable(tmp_path, monkeypatch):
    path = tmp_path / 'workflow.json'; path.write_text('{"1": {}}')
    def unavailable(*args):
        raise render_task.ComfyUnavailable('offline')
    monkeypatch.setattr(render_task, 'render', unavailable)
    result = render_task.make_render_executor(path, tmp_path)(SimpleNamespace(task_id='t', objective='render: orman'), 'artist')
    assert not result.success and not result.artifacts
    assert result.summary == 'ComfyUI kapalı: http://127.0.0.1:8188'

def test_empty_delivery_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'workflow.json'; path.write_text('{"1": {}}')
    monkeypatch.setattr(render_task, 'render', lambda *args: [])
    result = render_task.make_render_executor(path, tmp_path)(SimpleNamespace(task_id='t', title='orman'), 'artist')
    assert not result.success and result.summary == '0 dosya üretildi'



def test_empty_render_prompt_fails_before_calling_comfy(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"1":{"text":"{{prompt}}"}}', encoding="utf-8")
    attempted = []
    monkeypatch.setattr(render_task, "render", lambda *args: attempted.append(args))
    result = render_task.make_render_executor(workflow, tmp_path)(
        SimpleNamespace(task_id="empty", objective="render:   "), "artist"
    )
    assert result.success is False
    assert not result.artifacts
    assert "boş prompt" in result.summary
    assert attempted == []


def test_render_outside_output_dir_is_never_delivered(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"1":{"text":"{{prompt}}"}}', encoding="utf-8")
    out_dir = tmp_path / "renders"
    out_dir.mkdir()
    outside = tmp_path / "external.png"
    outside.write_bytes(b"not an authorized artifact")
    monkeypatch.setattr(render_task, "render", lambda *args: [outside])
    result = render_task.make_render_executor(workflow, out_dir)(
        SimpleNamespace(task_id="outside", objective="render: woodland"), "artist"
    )
    assert result.success is False
    assert not result.artifacts


def test_zero_byte_render_is_not_success(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"1":{"text":"{{prompt}}"}}', encoding="utf-8")
    empty = tmp_path / "image.png"
    empty.touch()
    monkeypatch.setattr(render_task, "render", lambda *args: [empty])
    result = render_task.make_render_executor(workflow, tmp_path)(
        SimpleNamespace(task_id="zero", objective="render: forest"), "artist"
    )
    assert result.success is False
    assert not result.artifacts



def test_non_media_artifact_is_not_reported_as_success(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"1":{"text":"{{prompt}}"}}', encoding="utf-8")
    non_media = tmp_path / "debug.txt"
    non_media.write_bytes(b"log information only")
    monkeypatch.setattr(render_task, "render", lambda *args: [non_media])
    result = render_task.make_render_executor(workflow, tmp_path)(
        SimpleNamespace(task_id="not-media", objective="render: woodland"), "artist"
    )
    assert result.success is False
    assert not result.artifacts
