"""Fail-closed ComfyUI delivery checks; all artifacts are isolated to tmp_path."""
import json
from types import SimpleNamespace

import pytest
from ahos import comfy_bridge, render_task


def test_comfy_error_history_is_not_completed(monkeypatch):
    monkeypatch.setattr(comfy_bridge, "_request", lambda *a, **kw: {
        "job": {"status": {"status_str": "error", "completed": False},
                "outputs": {"7": {"images": [{"filename": "stale.png"}]}}}
    })
    with pytest.raises(RuntimeError, match="error"):
        comfy_bridge.wait("job", poll_s=0)


def test_comfy_running_history_is_not_completed(monkeypatch):
    records = iter([
        {"job": {"status": {"status_str": "running", "completed": False}}},
        {"job": {"status": {"status_str": "success", "completed": True},
                 "outputs": {"7": {"videos": [{"filename": "ok.mp4"}]}}}},
    ])
    monkeypatch.setattr(comfy_bridge, "_request", lambda *a, **kw: next(records))
    result = comfy_bridge.wait("job", poll_s=0)
    assert result["status"]["completed"] is True


def test_placeholder_text_to_video_is_blocked(tmp_path, monkeypatch):
    workflow = tmp_path / "ltx2_text2video.json"
    workflow.write_text(json.dumps({"1": {"class_type": "SaveImage", "inputs": {}}}))
    monkeypatch.setattr(render_task, "render", lambda *a: pytest.fail("must not submit fake video graph"))
    result = render_task.make_render_executor(workflow, tmp_path)(
        SimpleNamespace(task_id="demo", objective="render: test"), "artist")
    assert not result.success and not result.artifacts
    assert "video workflow" in result.summary


def test_video_workflow_requires_real_mp4_signature(tmp_path, monkeypatch):
    workflow = tmp_path / "video.json"
    workflow.write_text(json.dumps({"1": {"class_type": "SaveVideo", "inputs": {}}}))
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"not a playable video")
    monkeypatch.setattr(render_task, "render", lambda *a: [clip])
    executor = render_task.make_render_executor(workflow, tmp_path)
    item = SimpleNamespace(task_id="demo", objective="render: forest")
    rejected = executor(item, "artist")
    assert not rejected.success and not rejected.artifacts
    clip.write_bytes(b"\x00\x00\x00\x18ftypisomTEST")
    accepted = executor(item, "artist")
    assert accepted.success and accepted.artifacts == (str(clip),)


def test_image_with_only_png_extension_does_not_pass(tmp_path, monkeypatch):
    workflow = tmp_path / "still.json"
    workflow.write_text(json.dumps({"1": {"class_type": "SaveImage", "inputs": {}}}))
    image = tmp_path / "fake.png"
    image.write_bytes(b"this is not a png image")
    monkeypatch.setattr(render_task, "render", lambda *a: [image])
    result = render_task.make_render_executor(workflow, tmp_path)(
        SimpleNamespace(task_id="fake", objective="render: trees"), "artist")
    assert not result.success and not result.artifacts
