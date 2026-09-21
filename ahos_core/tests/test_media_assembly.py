import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from ahos.episode_assembly import EpisodeAssemblyPlanner, ReleaseAsset
from ahos.media_assembly import MediaAssemblyError, ProfessionalMediaAssembler


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration test requires ffmpeg and ffprobe",
)


def run(command):
    subprocess.run(command, check=True, capture_output=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_media(tmp_path: Path):
    videos = []
    for index, color in enumerate(("red", "blue"), start=1):
        path = tmp_path / f"shot-{index}.mkv"
        run(("ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"color={color}:s=320x180:d=1:r=24", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv420p", str(path)))
        videos.append(path)
    audio = tmp_path / "tr.wav"
    run(("ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(audio)))
    subtitle = tmp_path / "tr.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,500\nMerhaba dünya.\n", encoding="utf-8")
    return videos, audio, subtitle


def package(tmp_path: Path):
    videos, audio, subtitle = build_media(tmp_path)
    assets = [
        ReleaseAsset(f"video-{i}", "video", str(path), 1.0, content_hash=digest(path))
        for i, path in enumerate(videos, start=1)
    ]
    assets.extend((
        ReleaseAsset("mix-tr", "final_mix", str(audio), 2.0, "tr", digest(audio)),
        ReleaseAsset("sub-tr", "subtitle", str(subtitle), None, "tr", digest(subtitle)),
    ))
    graph = {
        "episode_id": "S01E001",
        "target_duration_seconds": 2,
        "shots": [{"output_asset_id": "video-1"}, {"output_asset_id": "video-2"}],
    }
    return EpisodeAssemblyPlanner().build(
        graph=graph, assets=assets, child_safe_approved=True, continuity_approved=True
    )


def test_real_ffmpeg_assembly_hashes_sources_and_probes_master(tmp_path: Path):
    evidence = ProfessionalMediaAssembler().assemble(
        package(tmp_path), tmp_path / "release.mkv", required_languages=("tr",)
    )
    assert len(evidence.output_sha256) == 64
    assert evidence.output_probe.video_streams == 1
    assert evidence.output_probe.audio_streams == 1
    assert evidence.output_probe.subtitle_streams == 1
    assert evidence.to_payload()["schema"] == "ahos.media-assembly-evidence.v1"


def test_changed_asset_bytes_are_rejected_before_assembly(tmp_path: Path):
    release = package(tmp_path)
    Path(next(a.path for a in release.assets if a.asset_id == "sub-tr")).write_text("changed")
    with pytest.raises(MediaAssemblyError, match="hash mismatch"):
        ProfessionalMediaAssembler().assemble(
            release, tmp_path / "release.mkv", required_languages=("tr",)
        )


def test_missing_language_assets_fail_closed(tmp_path: Path):
    with pytest.raises(MediaAssemblyError, match="de"):
        ProfessionalMediaAssembler().assemble(
            package(tmp_path), tmp_path / "release.mkv", required_languages=("tr", "de")
        )
