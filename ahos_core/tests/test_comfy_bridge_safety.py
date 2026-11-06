"""Comfy download safety. All tests use temporary paths and mocked transport."""
from __future__ import annotations

from io import BytesIO

from ahos import comfy_bridge


def test_download_does_not_overwrite_previous_render(tmp_path, monkeypatch):
    previous = tmp_path / "clip.png"
    previous.write_bytes(b"previous-important-render")
    calls = []

    def fake_urlopen(request_url, timeout):
        calls.append(request_url)
        return BytesIO(b"new-valid-byte-stream")

    monkeypatch.setattr(comfy_bridge.urllib.request, "urlopen", fake_urlopen)
    record = {"outputs": {"7": {"images": [{"filename": "clip.png"}]}}}
    saved = comfy_bridge.download(record, tmp_path)
    assert previous.read_bytes() == b"previous-important-render"
    assert len(saved) == 1
    assert saved[0] == tmp_path / "clip_1.png"
    assert saved[0].read_bytes() == b"new-valid-byte-stream"
    assert len(calls) == 1


def test_empty_comfy_download_is_not_reported_as_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(
        comfy_bridge.urllib.request, "urlopen",
        lambda *args, **kwargs: BytesIO(b""),
    )
    record = {"outputs": {"7": {"images": [{"filename": "empty.png"}]}}}
    assert comfy_bridge.download(record, tmp_path) == []
    assert not (tmp_path / "empty.png").exists()


def test_download_transport_error_preserves_previous_file(tmp_path, monkeypatch):
    existing = tmp_path / "shot.png"
    existing.write_bytes(b"keep-me")

    def broken_urlopen(*args, **kwargs):
        raise OSError("mock network error")

    monkeypatch.setattr(comfy_bridge.urllib.request, "urlopen", broken_urlopen)
    record = {"outputs": {"7": {"images": [{"filename": "shot.png"}]}}}
    assert comfy_bridge.download(record, tmp_path) == []
    assert existing.read_bytes() == b"keep-me"
    assert not (tmp_path / "shot_1.png").exists()
