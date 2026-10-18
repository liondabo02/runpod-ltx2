from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class AudioPostError(ValueError):
    pass


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _srt_time(seconds: float) -> str:
    if seconds < 0:
        raise AudioPostError("timestamps cannot be negative")
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


@dataclass(frozen=True, slots=True)
class DialogueTiming:
    line_id: str
    speaker_id: str
    text: str
    start_seconds: float
    end_seconds: float
    rendered_duration_seconds: float

    @property
    def slot_duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class DubFit:
    line_id: str
    ratio: float
    action: str
    accepted: bool


@dataclass(frozen=True, slots=True)
class MixInstruction:
    stem: str
    target_lufs: float
    peak_ceiling_dbtp: float
    dialogue_ducking_db: float


@dataclass(frozen=True, slots=True)
class AudioPostPackage:
    episode_id: str
    language: str
    subtitle_cues: tuple[DialogueTiming, ...]
    dub_fits: tuple[DubFit, ...]
    mix_instructions: tuple[MixInstruction, ...]
    qa: Mapping[str, bool]
    package_hash: str

    @property
    def ready(self) -> bool:
        return all(self.qa.values())


class AudioPostProductionPlanner:
    """Plans subtitles, conservative dub fitting, and mix QA without rendering."""

    def plan(
        self,
        *,
        episode_id: str,
        language: str,
        episode_duration_seconds: float,
        dialogue: Sequence[DialogueTiming],
        child_speaker_ids: Iterable[str] = (),
    ) -> AudioPostPackage:
        if not episode_id.strip() or not language.strip():
            raise AudioPostError("episode_id and language are required")
        if episode_duration_seconds <= 0:
            raise AudioPostError("episode duration must be positive")
        if not dialogue:
            raise AudioPostError("at least one dialogue timing is required")

        children = frozenset(child_speaker_ids)
        ordered = tuple(sorted(dialogue, key=lambda item: (item.start_seconds, item.line_id)))
        seen: set[str] = set()
        timeline_valid = True
        text_complete = True
        fits: list[DubFit] = []

        for item in ordered:
            if item.line_id in seen:
                raise AudioPostError(f"duplicate line id: {item.line_id}")
            seen.add(item.line_id)
            if (
                item.start_seconds < 0
                or item.end_seconds <= item.start_seconds
                or item.end_seconds > episode_duration_seconds
                or item.rendered_duration_seconds <= 0
            ):
                timeline_valid = False
            if not item.text.strip():
                text_complete = False

            slot = item.slot_duration_seconds
            ratio = item.rendered_duration_seconds / slot if slot > 0 else float("inf")
            if 0.90 <= ratio <= 1.05:
                action, accepted = "none", True
            elif 0.80 <= ratio <= 1.15 and item.speaker_id not in children:
                action, accepted = "time_stretch", True
            else:
                # Child voices are never automatically time-stretched; extreme adult
                # mismatches also return to translation/dialogue editing.
                action, accepted = "rewrite_or_rerecord", False
            fits.append(DubFit(item.line_id, round(ratio, 4), action, accepted))

        mix = (
            MixInstruction("dialogue", -16.0, -1.0, 0.0),
            MixInstruction("music", -24.0, -2.0, -8.0),
            MixInstruction("sfx", -22.0, -2.0, -4.0),
            MixInstruction("master", -16.0, -1.0, 0.0),
        )
        qa = {
            "timeline_valid": timeline_valid,
            "subtitle_text_complete": text_complete,
            "dub_length_fit": all(fit.accepted for fit in fits),
            "child_voice_protected": all(
                fit.action != "time_stretch"
                for fit, item in zip(fits, ordered, strict=True)
                if item.speaker_id in children
            ),
            "mix_targets_present": {item.stem for item in mix}
            == {"dialogue", "music", "sfx", "master"},
        }
        semantic = {
            "episode_id": episode_id,
            "language": language,
            "duration": episode_duration_seconds,
            "dialogue": [
                {
                    "line_id": item.line_id,
                    "speaker_id": item.speaker_id,
                    "text": item.text,
                    "start": item.start_seconds,
                    "end": item.end_seconds,
                    "rendered_duration": item.rendered_duration_seconds,
                }
                for item in ordered
            ],
            "fits": [
                {"line_id": fit.line_id, "ratio": fit.ratio, "action": fit.action}
                for fit in fits
            ],
            "mix": [
                {
                    "stem": item.stem,
                    "target_lufs": item.target_lufs,
                    "peak_ceiling_dbtp": item.peak_ceiling_dbtp,
                    "dialogue_ducking_db": item.dialogue_ducking_db,
                }
                for item in mix
            ],
            "qa": qa,
        }
        return AudioPostPackage(
            episode_id=episode_id,
            language=language,
            subtitle_cues=ordered,
            dub_fits=tuple(fits),
            mix_instructions=mix,
            qa=qa,
            package_hash=_digest(semantic),
        )


def export_srt(package: AudioPostPackage, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for index, cue in enumerate(package.subtitle_cues, start=1):
        blocks.append(
            f"{index}\n{_srt_time(cue.start_seconds)} --> {_srt_time(cue.end_seconds)}\n{cue.text}"
        )
    output.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output
