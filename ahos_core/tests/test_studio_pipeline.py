"""Çizgi film hattı: brief → bölüm → kapı; sahip komutundan üretim."""

from __future__ import annotations

import json
from pathlib import Path

from ahos.owner_cli import main as owner_main
from ahos.studio_pipeline import produce_episode, storyboard


def test_storyboard_is_deterministic():
    first = storyboard("parkta bir gün", scenes=3, seconds=2.0)
    second = storyboard("parkta bir gün", scenes=3, seconds=2.0)

    assert [s.scene_id for s in first.scenes] == [s.scene_id for s in second.scenes]
    assert first.title == second.title
    assert abs(first.duration() - second.duration()) < 1e-9
    assert len(first.scenes) == 3
    assert all(scene.lines for scene in first.scenes)


def test_produce_episode_without_voice_passes_the_gate(tmp_path):
    episode = storyboard("deneme", scenes=1, seconds=2.0)
    report = produce_episode(episode, tmp_path, use_voice=False)

    assert report["passed"] is True, report
    assert (tmp_path / "episode.mp4").is_file()
    assert (tmp_path / "episode.srt").is_file()
    assert (tmp_path / "brief.json").is_file()
    assert (tmp_path / "story.json").is_file()

    stored = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert stored["passed"] is True
    assert stored["voice"] is None


def test_owner_command_produces_an_episode(tmp_path):
    code = owner_main([
        "--runtime-dir", str(tmp_path / "runtime"),
        "--scenes", "1", "--seconds", "1", "--no-voice",
        "çizgi film: kısa bir test",
    ])

    assert code == 0
    episodes = list((tmp_path / "runtime" / "studio-episodes").glob("*/episode.mp4"))
    assert len(episodes) == 1
    acceptance = json.loads(episodes[0].with_name("acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["passed"] is True


def test_provider_registry_resolves_free_local_first():
    """Katalogdan seçim: ücretsiz/yerel sağlayıcı, ücretliden önce gelir."""

    from ahos.studio_department import ProviderRegistry

    registry = ProviderRegistry.load()
    chosen = registry.resolve("video.generate", "tr")
    assert chosen is not None
    assert chosen.paid is False
    assert chosen.adapter
    assert chosen.model_ref


def test_provider_registry_requires_approval_for_paid():
    """Ücretsiz varsayılan korunur; ücretli yol yalnızca onay+bütçe izniyle açılır."""

    from ahos.studio_department import ProviderRegistry

    registry = ProviderRegistry.load()
    default = registry.resolve("video.generate", "tr")
    assert default is not None and default.paid is False

    paid_only = ProviderRegistry.from_payload({"providers": [{
        "provider_id": "paid-video",
        "task_types": ["video.generate"],
        "adapter": "external_adapter",
        "languages": ["tr"],
        "paid": True,
        "external": True,
        "commercial_default": False,
        "priority": 1,
        "model_ref": "config://paid/video",
    }]})
    assert paid_only.resolve("video.generate", "tr") is None
    assert paid_only.resolve("video.generate", "tr", allow_paid=True) is None
    approved = paid_only.resolve("video.generate", "tr", allow_paid=True,
                                 approval="owner-approved-123")
    assert approved is not None and approved.paid is True



def _ffmpeg_clip(path, *, source, seconds, audio=False):
    """Deterministik test klibi: PIL kareleri (hareketli/durgun) + isteğe bağlı ton."""

    import array
    import math
    import shutil
    import subprocess
    import wave

    from PIL import Image, ImageDraw

    if not shutil.which("ffmpeg"):
        import pytest

        pytest.skip("ffmpeg yok")
    fps = 24
    total = max(1, int(seconds * fps))
    static = source.startswith("color")
    frames = path.parent / f"frames-{path.stem}"
    frames.mkdir(parents=True, exist_ok=True)
    for index in range(total):
        image = Image.new("RGB", (320, 180), (0, 0, 200) if static else (30, 60, 120))
        if not static:
            draw = ImageDraw.Draw(image)
            x = 20 + (index * 6) % 250
            draw.rectangle([x, 60, x + 60, 120], fill=(240, 200, 60))
        image.save(frames / f"f{index:04d}.png")

    args = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
            "-i", str(frames / "f%04d.png")]
    if audio:
        tone = path.parent / f"tone-{path.stem}.wav"
        with wave.open(str(tone), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(array.array("h", [
                int(8000 * math.sin(2 * math.pi * 440 * i / 16000))
                for i in range(int(seconds * 16000))]).tobytes())
        args += ["-i", str(tone), "-c:a", "aac", "-strict", "-2", "-ar", "48000",
                 "-shortest"]
    args += ["-pix_fmt", "yuv420p", "-r", str(fps), str(path)]
    subprocess.run(args, check=True, capture_output=True)
    return path



def test_static_clip_fails_motion_gate(tmp_path):
    from ahos.studio_qa import verify_production

    clip = _ffmpeg_clip(tmp_path / "static.mp4", source="color=c=blue", seconds=3)
    report = verify_production(clip, expected_seconds=3.0, expects_voice=False)
    assert report["checks"]["motion_ok"] is False
    assert report["passed"] is False
    assert report["measurements"]["motion_score"] < 0.02


def test_duration_mismatch_fails(tmp_path):
    from ahos.studio_qa import verify_production

    clip = _ffmpeg_clip(tmp_path / "moving.mp4", source="testsrc2", seconds=2)
    report = verify_production(clip, expected_seconds=6.0, expects_voice=False)
    assert report["checks"]["duration_ok"] is False
    assert report["passed"] is False


def test_missing_voice_fails_when_expected(tmp_path):
    from ahos.studio_qa import verify_production

    clip = _ffmpeg_clip(tmp_path / "moving.mp4", source="testsrc2", seconds=2)
    report = verify_production(clip, expected_seconds=2.0, expects_voice=True)
    assert report["checks"]["audio_ok"] is False
    assert report["passed"] is False


def test_moving_clip_with_audio_passes(tmp_path):
    from ahos.studio_qa import verify_production

    clip = _ffmpeg_clip(tmp_path / "good.mp4", source="testsrc2", seconds=3, audio=True)
    report = verify_production(clip, expected_seconds=3.0, expects_voice=True,
                               min_cuts=0, loudness_range=(-60.0, 0.0))
    assert report["checks"]["motion_ok"] is True
    assert report["checks"]["audio_ok"] is True
    assert report["passed"] is True, report


def test_cli_dry_run_makes_zero_provider_calls(tmp_path, monkeypatch):
    """--dry-run: plan + maliyet üretir, sağlayıcı çağrısı yapmaz."""

    import json

    from ahos import series_cli

    calls = {"n": 0}
    monkeypatch.setattr(series_cli, "produce_episode",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    code = series_cli.main(["--root", str(tmp_path), "--dry-run", "produce", "--episode", "1"])

    assert code == 0
    assert calls["n"] == 0
    payload = json.loads((tmp_path / "episodes" / "b01" / "dry-run.json")
                         .read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["cost"]["total_cost"] >= 0.0


def test_cli_resume_skips_verified_episode(tmp_path, monkeypatch):
    """--resume: doğrulanmış bölüm varsa üretim çağrılmaz."""

    from ahos import series_cli

    calls = {"n": 0}
    monkeypatch.setattr(series_cli, "produce_episode",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    target = tmp_path / "episodes" / "b01"
    target.mkdir(parents=True)
    (target / "episode.mp4").write_bytes(b"x")

    code = series_cli.main(["--root", str(tmp_path), "--resume", "produce", "--episode", "1"])
    assert code == 0
    assert calls["n"] == 0


def test_cli_budget_gate_blocks_before_production(tmp_path, monkeypatch):
    """Üretimden önce maliyet kapısı: bütçe aşımı exit 4 + çağrı yok."""

    from ahos import series_cli

    calls = {"n": 0}
    monkeypatch.setattr(series_cli, "produce_episode",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(series_cli, "_cost_estimate",
                        lambda episode: {"total_cost": 5.0, "currency": "USD", "lines": []})

    code = series_cli.main(["--root", str(tmp_path), "--max-cost", "1",
                            "produce", "--episode", "1"])
    assert code == 4
    assert calls["n"] == 0


def test_cli_preflight_failure_blocks_with_checklist(tmp_path, monkeypatch):
    """Preflight başarısızsa non-zero döner ve checklist yazar."""

    from ahos import series_cli

    monkeypatch.setattr(series_cli, "_preflight", lambda require_comfy=False: (
        False, [{"check": "ffmpeg", "ok": False, "hint": "PATH'e ekleyin"}]))
    code = series_cli.main(["--root", str(tmp_path), "produce", "--episode", "1"])
    assert code == 3




def test_provider_registry_fails_closed_on_bad_catalog():
    """Eksik/çift kayıt sessizce geçmez; katalog hatası yükselir."""

    import pytest

    from ahos.studio_department import ProviderRegistry, ProviderRegistryError

    with pytest.raises(ProviderRegistryError):
        ProviderRegistry.from_payload({"providers": [{"provider_id": "x"}]})

    with pytest.raises(ProviderRegistryError):
        ProviderRegistry.from_payload({"providers": []})



def test_stage_gate_blocks_downstream_without_evidence(tmp_path):
    """Evidence yoksa stage PASS olmaz; sonraki aşamalar blocked işaretlenir."""

    from ahos.studio_department import stage_gate

    report = stage_gate(tmp_path)
    assert report["ready"] is False
    assert report["blocked_at"] == "brief"
    assert "story" in report["blocked"]

    (tmp_path / "brief.json").write_text("{}", encoding="utf-8")
    (tmp_path / "story.json").write_text("{}", encoding="utf-8")
    partial = stage_gate(tmp_path)
    assert partial["stages"][0]["ok"] is True
    assert partial["blocked_at"] == "voice"


def test_release_gate_requires_video_ledger_and_budget(tmp_path):
    """Teslim: video + ledger + bütçe birlikte; eksikse passed=False."""

    import json

    from ahos.release_gate import verify_release

    assert verify_release(tmp_path)["passed"] is False

    (tmp_path / "episode.mp4").write_bytes(b"\x00" * 120_000)
    ledger = {"passed": True, "stages": [{"stage": "qa", "status": "passed"}],
              "cost": {"total_cost": 0.0}}
    (tmp_path / "production-ledger.json").write_text(
        json.dumps(ledger), encoding="utf-8")

    assert verify_release(tmp_path, episode_cap=1.0)["passed"] is True
    assert verify_release(tmp_path, episode_cap=-1.0)["passed"] is False

