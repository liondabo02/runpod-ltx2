from __future__ import annotations

import sys
from pathlib import Path

from ahos.adapters import tts


def test_edge_voice_writes_file(tmp_path, monkeypatch) -> None:
    target = tmp_path / "ses.mp3"

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        target.write_bytes(b"x" * 5000)
        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    result = tts.edge_voice("merhaba", target)

    assert result.ok is True
    assert result.provider == "edge-tts"
    assert target.exists()


def test_edge_voice_rejects_tiny_file(tmp_path, monkeypatch) -> None:
    target = tmp_path / "ses.mp3"

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        target.write_bytes(b"x" * 10)
        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    result = tts.edge_voice("merhaba", target)

    assert result.ok is False
    assert "küçük" in result.detail


def test_synthesize_rejects_empty_text(tmp_path) -> None:
    result = tts.synthesize("   ", tmp_path / "x.mp3")

    assert result.ok is False
    assert "boş" in result.detail


def test_synthesize_reports_all_providers_failed(tmp_path) -> None:
    def failing(text, target, voice):
        return tts.TtsResult(False, "", "edge-tts", "ağ yok")

    result = tts.synthesize("merhaba", tmp_path / "x.mp3", edge=failing)

    assert result.ok is False
    assert "hiçbir sağlayıcı" in result.detail
