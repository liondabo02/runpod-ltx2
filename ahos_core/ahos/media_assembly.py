from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .episode_assembly import EpisodeReleasePackage, ReleaseAsset


class MediaAssemblyError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MediaProbe:
    path: str
    duration_seconds: float
    format_name: str
    video_streams: int
    audio_streams: int
    subtitle_streams: int


@dataclass(frozen=True, slots=True)
class AssemblyEvidence:
    episode_id: str
    output_path: str
    output_sha256: str
    output_probe: MediaProbe
    source_sha256: tuple[tuple[str, str], ...]
    ffmpeg_command: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.media-assembly-evidence.v1",
            "episode_id": self.episode_id,
            "output_path": self.output_path,
            "output_sha256": self.output_sha256,
            "output_probe": {
                "path": self.output_probe.path,
                "duration_seconds": self.output_probe.duration_seconds,
                "format_name": self.output_probe.format_name,
                "video_streams": self.output_probe.video_streams,
                "audio_streams": self.output_probe.audio_streams,
                "subtitle_streams": self.output_probe.subtitle_streams,
            },
            "source_sha256": dict(self.source_sha256),
            "ffmpeg_command": list(self.ffmpeg_command),
        }


CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command), capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaAssemblyError(f"media command failed to start: {exc}") from exc


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProfessionalMediaAssembler:
    """Verifies local media bytes and creates a deterministic MKV release master."""

    def __init__(
        self,
        *,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        runner: CommandRunner = _run,
        timeout_seconds: float = 300.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def probe(self, path: str | Path) -> MediaProbe:
        media = Path(path).resolve()
        if not media.is_file():
            raise MediaAssemblyError(f"media file does not exist: {media}")
        command = (
            self.ffprobe, "-v", "error", "-show_entries",
            "format=duration,format_name:stream=codec_type", "-of", "json", str(media),
        )
        result = self.runner(command, self.timeout_seconds)
        if result.returncode != 0:
            raise MediaAssemblyError(f"ffprobe failed for {media}: {result.stderr.strip()}")
        try:
            payload = json.loads(result.stdout)
            streams = payload.get("streams", [])
            fmt = payload["format"]
            duration = float(fmt["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MediaAssemblyError(f"invalid ffprobe response for {media}") from exc
        kinds = [item.get("codec_type") for item in streams if isinstance(item, dict)]
        return MediaProbe(
            str(media), duration, str(fmt.get("format_name", "")),
            kinds.count("video"), kinds.count("audio"), kinds.count("subtitle"),
        )

    @staticmethod
    def _verified_path(asset: ReleaseAsset) -> tuple[Path, str]:
        path = Path(asset.path).resolve()
        if not path.is_file():
            raise MediaAssemblyError(f"asset file does not exist: {asset.asset_id}")
        actual = sha256_file(path)
        expected = (asset.content_hash or "").lower()
        if len(expected) != 64 or expected != actual:
            raise MediaAssemblyError(f"asset hash mismatch: {asset.asset_id}")
        return path, actual

    def assemble(
        self,
        package: EpisodeReleasePackage,
        output_path: str | Path,
        *,
        required_languages: Sequence[str],
        overwrite: bool = False,
    ) -> AssemblyEvidence:
        if not package.release_ready:
            raise MediaAssemblyError("release package has not passed planning QA")
        languages = tuple(required_languages)
        if not languages or len(languages) != len(set(languages)):
            raise MediaAssemblyError("required languages must be unique and non-empty")
        target = Path(output_path).resolve()
        if target.suffix.lower() != ".mkv":
            raise MediaAssemblyError("professional release master must use .mkv")
        if target.exists() and not overwrite:
            raise MediaAssemblyError(f"output already exists: {target}")

        append_ids = [
            str(step["asset_id"])
            for step in package.assembly_steps
            if step.get("operation") == "append_video"
        ]
        by_id = {asset.asset_id: asset for asset in package.assets}
        videos = [by_id[item] for item in append_ids if item in by_id]
        if len(videos) != len(append_ids) or not videos:
            raise MediaAssemblyError("ordered picture assets are incomplete")

        audio: list[ReleaseAsset] = []
        subtitles: list[ReleaseAsset] = []
        for language in languages:
            mixes = [a for a in package.assets if a.kind == "final_mix" and a.language == language]
            subs = [a for a in package.assets if a.kind == "subtitle" and a.language == language]
            if len(mixes) != 1 or len(subs) != 1:
                raise MediaAssemblyError(f"exactly one mix and subtitle required for {language}")
            audio.append(mixes[0])
            subtitles.append(subs[0])

        verified: dict[str, tuple[Path, str]] = {}
        for asset in (*videos, *audio, *subtitles):
            verified[asset.asset_id] = self._verified_path(asset)
        for asset in videos:
            probe = self.probe(verified[asset.asset_id][0])
            if probe.video_streams != 1:
                raise MediaAssemblyError(f"picture asset must contain one video stream: {asset.asset_id}")

        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ahos-assembly-") as temp_dir:
            concat_file = Path(temp_dir) / "picture.ffconcat"
            lines = ["ffconcat version 1.0"]
            for asset in videos:
                escaped = str(verified[asset.asset_id][0]).replace("'", "'\\''")
                lines.append(f"file '{escaped}'")
            concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            command: list[str] = [
                self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y" if overwrite else "-n",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
            ]
            for asset in audio:
                command.extend(("-i", str(verified[asset.asset_id][0])))
            for asset in subtitles:
                command.extend(("-i", str(verified[asset.asset_id][0])))
            command.extend(("-map", "0:v:0"))
            for index, language in enumerate(languages, start=1):
                command.extend(("-map", f"{index}:a:0", f"-metadata:s:a:{index - 1}", f"language={language}"))
            subtitle_offset = 1 + len(audio)
            for index, language in enumerate(languages):
                command.extend(("-map", f"{subtitle_offset + index}:0", f"-metadata:s:s:{index}", f"language={language}"))
            command.extend((
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-c:s", "srt",
                "-metadata", f"title={package.episode_id}", str(target),
            ))
            result = self.runner(tuple(command), self.timeout_seconds)
            if result.returncode != 0:
                raise MediaAssemblyError(f"ffmpeg assembly failed: {result.stderr.strip()}")

        output_probe = self.probe(target)
        if output_probe.video_streams != 1:
            raise MediaAssemblyError("assembled master must contain one video stream")
        if output_probe.audio_streams != len(languages) or output_probe.subtitle_streams != len(languages):
            raise MediaAssemblyError("assembled master stream counts do not match release languages")
        if abs(output_probe.duration_seconds - package.target_duration_seconds) > 0.5:
            raise MediaAssemblyError("assembled master duration is outside tolerance")
        return AssemblyEvidence(
            package.episode_id,
            str(target),
            sha256_file(target),
            output_probe,
            tuple(sorted((asset_id, digest) for asset_id, (_, digest) in verified.items())),
            tuple(command),
        )

