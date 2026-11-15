import json
from types import SimpleNamespace
from ahos import render_task

def test_success_and_prompt_escaping(tmp_path, monkeypatch):
    workflow = tmp_path / 'workflow.json'
    workflow.write_text(json.dumps({'1': {'text': '{{prompt}}', 'seed': '{{seed}}'}}))
    output = tmp_path / 'frame.png'
    output.write_bytes(b'\x89PNG\r\n\x1a\n' + b'valid-png-test')
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


def _tiny_episode():
    from ahos.studio_2d import Episode, Line, Scene

    return Episode(title="t", scenes=[Scene(
        scene_id="s1", setting="Açılış", background="day", characters=["aden"],
        lines=[Line("s1", "aden", "merhaba", 2.0)])])


def _write_fake_mp4(path, size=128):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * max(0, size - 12))
    return path


def test_generate_clips_writes_manifest_and_verifies(tmp_path, monkeypatch):
    import json

    from ahos import comfy_bridge, visual_pipeline

    calls = {"n": 0}

    def fake_render(workflow, out_dir):
        calls["n"] += 1
        return [_write_fake_mp4(tmp_path / "out" / "s1-01" / "clip.mp4")]

    monkeypatch.setattr(comfy_bridge, "render", fake_render)
    monkeypatch.setattr(comfy_bridge, "fill_template",
                        lambda *a, **k: {"1": {"class_type": "SaveVideo", "inputs": {}}})
    clips = visual_pipeline.generate_clips(
        _tiny_episode(), tmp_path / "workflow.json", tmp_path / "out", style="cartoon")

    assert calls["n"] == 1
    assert len(clips) == 1
    manifest = json.loads((tmp_path / "out" / "s1-01" / "job.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "verified"
    assert manifest["attempts"] == 1
    assert manifest["prompt"] and manifest["negative_prompt"] and manifest["seed"] is not None
    assert manifest["output_path"].endswith("clip.mp4")


def test_generate_clips_resume_skips_verified_shots(tmp_path, monkeypatch):
    from ahos import comfy_bridge, visual_pipeline

    calls = {"n": 0}

    def fake_render(workflow, out_dir):
        calls["n"] += 1
        return [_write_fake_mp4(tmp_path / "out" / "s1-01" / "clip.mp4")]

    monkeypatch.setattr(comfy_bridge, "render", fake_render)
    monkeypatch.setattr(comfy_bridge, "fill_template",
                        lambda *a, **k: {"1": {"class_type": "SaveVideo", "inputs": {}}})
    first = visual_pipeline.generate_clips(_tiny_episode(), tmp_path / "wf.json", tmp_path / "out")
    second = visual_pipeline.generate_clips(_tiny_episode(), tmp_path / "wf.json", tmp_path / "out")

    assert calls["n"] == 1          # ikinci koşuda sağlayıcı çağrılmadı
    assert first == second


def test_generate_clips_classifies_invalid_output(tmp_path, monkeypatch):
    import pytest

    from ahos import comfy_bridge, visual_pipeline

    monkeypatch.setattr(comfy_bridge, "render", lambda workflow, out_dir: [])
    monkeypatch.setattr(comfy_bridge, "fill_template",
                        lambda *a, **k: {"1": {"class_type": "SaveVideo", "inputs": {}}})
    with pytest.raises(comfy_bridge.ComfyStageError) as caught:
        visual_pipeline.generate_clips(_tiny_episode(), tmp_path / "wf.json", tmp_path / "out")
    info = caught.value.info
    assert info["failure_class"] == "invalid_output"
    assert info["action"] == "fallback"


def test_valid_artifact_rejects_fake_and_accepts_real_header(tmp_path):
    from ahos.render_task import _valid_artifact

    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not-a-video" * 10)
    assert _valid_artifact(bad, tmp_path, video_required=True) is False

    good = _write_fake_mp4(tmp_path / "good.mp4")
    assert _valid_artifact(good, tmp_path, video_required=True) is True

    outside = _write_fake_mp4(tmp_path.parent / "outside.mp4")
    assert _valid_artifact(outside, tmp_path, video_required=True) is False


def test_health_failure_raises_comfy_unavailable(monkeypatch):
    import pytest

    from ahos import comfy_bridge

    def boom(*_args, **_kwargs):
        raise comfy_bridge.ComfyUnavailable("down")

    monkeypatch.setattr(comfy_bridge, "_request", boom)
    with pytest.raises(comfy_bridge.ComfyUnavailable):
        comfy_bridge.health(timeout=0.1)


def test_classify_error_maps_actions():
    from ahos.comfy_bridge import classify_error

    assert classify_error("CUDA out of memory")["action"] == "retry"
    assert classify_error("queue is full")["action"] == "retry"
    assert classify_error("checkpoint not found")["action"] == "fallback"
    assert classify_error("401 unauthorized")["action"] == "block"

