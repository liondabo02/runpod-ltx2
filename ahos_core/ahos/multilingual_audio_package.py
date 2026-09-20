from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Sequence

from .audio_pipeline import DEFAULT_LANGUAGE_POLICIES


class MultilingualAudioPackageError(ValueError):
    pass


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AudioPackageAsset:
    asset_id: str
    kind: str
    uri: str
    sha256: str
    language: str | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class LanguagePackageStatus:
    language: str
    final_mix_present: bool
    subtitle_present: bool
    duration_matches: bool
    voice_enrollments_complete: bool

    @property
    def ready(self) -> bool:
        return (
            self.final_mix_present
            and self.subtitle_present
            and self.duration_matches
            and self.voice_enrollments_complete
        )


@dataclass(frozen=True, slots=True)
class MultilingualAudioPackage:
    episode_id: str
    required_languages: tuple[str, ...]
    language_statuses: tuple[LanguagePackageStatus, ...]
    assets: tuple[AudioPackageAsset, ...]
    shared_music_present: bool
    shared_sfx_present: bool
    package_hash: str

    @property
    def ready(self) -> bool:
        return (
            self.shared_music_present
            and self.shared_sfx_present
            and all(status.ready for status in self.language_statuses)
        )


class MultilingualAudioPackager:
    """Fail-closed manifest builder; performs no synthesis, mixing, or network I/O."""

    VALID_KINDS = frozenset({"final_mix", "subtitle", "music_stem", "sfx_stem"})

    def build(
        self,
        *,
        episode_id: str,
        episode_duration_seconds: float,
        speaking_character_ids: Iterable[str],
        canonical_voice_enrollments: Iterable[tuple[str, str]],
        assets: Sequence[AudioPackageAsset],
        required_languages: Iterable[str] | None = None,
    ) -> MultilingualAudioPackage:
        if not episode_id.strip() or episode_duration_seconds <= 0:
            raise MultilingualAudioPackageError("valid episode id and duration are required")
        languages = tuple(
            required_languages
            if required_languages is not None
            else (policy.code for policy in DEFAULT_LANGUAGE_POLICIES if policy.required)
        )
        if not languages or len(set(languages)) != len(languages):
            raise MultilingualAudioPackageError("required languages must be unique and non-empty")
        if len({asset.asset_id for asset in assets}) != len(assets):
            raise MultilingualAudioPackageError("asset ids must be unique")
        for asset in assets:
            if asset.kind not in self.VALID_KINDS:
                raise MultilingualAudioPackageError(f"unsupported asset kind: {asset.kind}")
            if len(asset.sha256) != 64 or any(c not in "0123456789abcdef" for c in asset.sha256.lower()):
                raise MultilingualAudioPackageError(f"invalid SHA-256 for {asset.asset_id}")

        speakers = frozenset(speaking_character_ids)
        enrollments = frozenset((character, language) for character, language in canonical_voice_enrollments)
        statuses: list[LanguagePackageStatus] = []
        for language in languages:
            mixes = [a for a in assets if a.kind == "final_mix" and a.language == language]
            subtitles = [a for a in assets if a.kind == "subtitle" and a.language == language]
            duration_matches = (
                len(mixes) == 1
                and mixes[0].duration_seconds is not None
                and abs(float(mixes[0].duration_seconds) - episode_duration_seconds) <= 0.05
            )
            statuses.append(
                LanguagePackageStatus(
                    language=language,
                    final_mix_present=len(mixes) == 1,
                    subtitle_present=len(subtitles) == 1,
                    duration_matches=duration_matches,
                    voice_enrollments_complete=all(
                        (speaker, language) in enrollments for speaker in speakers
                    ),
                )
            )

        music = [a for a in assets if a.kind == "music_stem" and a.language is None]
        sfx = [a for a in assets if a.kind == "sfx_stem" and a.language is None]
        semantic = {
            "episode_id": episode_id,
            "duration": episode_duration_seconds,
            "languages": languages,
            "statuses": [
                {
                    "language": s.language,
                    "mix": s.final_mix_present,
                    "subtitle": s.subtitle_present,
                    "duration": s.duration_matches,
                    "voices": s.voice_enrollments_complete,
                }
                for s in statuses
            ],
            "assets": [
                {"id": a.asset_id, "kind": a.kind, "uri": a.uri, "sha256": a.sha256,
                 "language": a.language, "duration": a.duration_seconds}
                for a in sorted(assets, key=lambda item: item.asset_id)
            ],
        }
        return MultilingualAudioPackage(
            episode_id=episode_id,
            required_languages=languages,
            language_statuses=tuple(statuses),
            assets=tuple(assets),
            shared_music_present=len(music) == 1,
            shared_sfx_present=len(sfx) == 1,
            package_hash=_hash(semantic),
        )
