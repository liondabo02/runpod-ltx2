from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .character_memory import CharacterBibleStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


class AudioPipelineError(RuntimeError):
    pass


class UnknownSpeakerError(AudioPipelineError):
    pass


class UnsupportedLanguageError(AudioPipelineError):
    pass


class AudioTaskType(str, Enum):
    DIALOGUE_TTS = "dialogue_tts"
    NARRATION_TTS = "narration_tts"
    MUSIC_CUE = "music_cue"
    SFX_CUE = "sfx_cue"
    MIX = "mix"
    LOCALIZATION_QA = "localization_qa"


@dataclass(frozen=True, slots=True)
class LanguagePolicy:
    code: str
    label: str
    required: bool
    human_review_required: bool = True


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    character_id: str
    voice_id: str
    provider_preference: tuple[str, ...]
    speaking_style: str = "age-appropriate, clear, warm"
    reference_audio_uri: str | None = None


@dataclass(frozen=True, slots=True)
class LocalizedDialogue:
    line_id: str
    episode_id: str
    scene_id: str
    speaker_character_id: str
    source_language: str
    target_language: str
    source_text: str
    localized_text: str
    localization_status: str


@dataclass(frozen=True, slots=True)
class AudioJob:
    job_id: str
    task_type: AudioTaskType
    episode_id: str
    scene_id: str
    language: str
    speaker_character_id: str | None
    provider_id: str | None
    payload: dict[str, object]
    paid: bool
    external: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "task_type": self.task_type.value,
            "episode_id": self.episode_id,
            "scene_id": self.scene_id,
            "language": self.language,
            "speaker_character_id": self.speaker_character_id,
            "provider_id": self.provider_id,
            "payload": self.payload,
            "paid": self.paid,
            "external": self.external,
        }


@dataclass(frozen=True, slots=True)
class AudioProviderDescriptor:
    provider_id: str
    name: str
    supported_languages: frozenset[str]
    capabilities: frozenset[str]
    paid: bool
    external: bool
    commercial_default: bool
    priority: int


class AudioProviderRegistry:
    def __init__(self, providers: Iterable[AudioProviderDescriptor]) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def list(self) -> tuple[AudioProviderDescriptor, ...]:
        return tuple(
            sorted(self._providers.values(), key=lambda p: (p.priority, p.provider_id))
        )

    def choose(
        self,
        *,
        language: str,
        capability: str,
        allow_paid: bool,
        allow_external: bool,
        commercial_use: bool,
        preferred: tuple[str, ...] = (),
    ) -> AudioProviderDescriptor:
        candidates = [
            provider
            for provider in self._providers.values()
            if language in provider.supported_languages
            and capability in provider.capabilities
            and (allow_paid or not provider.paid)
            and (allow_external or not provider.external)
            and (not commercial_use or provider.commercial_default)
        ]

        for preferred_id in preferred:
            for provider in candidates:
                if provider.provider_id == preferred_id:
                    return provider

        if not candidates:
            raise UnsupportedLanguageError(
                f"no allowed provider for language={language!r}, capability={capability!r}"
            )

        return sorted(candidates, key=lambda p: (p.priority, p.provider_id))[0]


def default_audio_provider_registry() -> AudioProviderRegistry:
    return AudioProviderRegistry(
        (
            AudioProviderDescriptor(
                provider_id="runpod-kokoro",
                name="Existing RunPod Kokoro TTS",
                supported_languages=frozenset({"en"}),
                capabilities=frozenset({"tts"}),
                paid=True,
                external=True,
                commercial_default=True,
                priority=30,
            ),
            AudioProviderDescriptor(
                provider_id="chatterbox-multilingual",
                name="Chatterbox Multilingual",
                supported_languages=frozenset(
                    {"tr", "de", "ar", "fr", "es", "en"}
                ),
                capabilities=frozenset({"tts", "voice_cloning"}),
                paid=True,
                external=True,
                commercial_default=True,
                priority=20,
            ),
            AudioProviderDescriptor(
                provider_id="fish-speech-s2",
                name="Fish Speech S2",
                supported_languages=frozenset(
                    {"en", "de", "ar", "fr", "es"}
                ),
                capabilities=frozenset({"tts", "voice_cloning"}),
                paid=True,
                external=True,
                commercial_default=False,
                priority=40,
            ),
            AudioProviderDescriptor(
                provider_id="f5-tts",
                name="F5-TTS",
                supported_languages=frozenset({"en", "de", "ar", "fr", "es"}),
                capabilities=frozenset({"tts", "voice_cloning"}),
                paid=True,
                external=True,
                commercial_default=False,
                priority=50,
            ),
        )
    )


DEFAULT_LANGUAGE_POLICIES = (
    LanguagePolicy("tr", "Turkish", True),
    LanguagePolicy("de", "German", True),
    LanguagePolicy("ar", "Arabic", True),
    LanguagePolicy("fr", "French", True),
    LanguagePolicy("es", "Spanish", True),
    LanguagePolicy("en", "English", True),
    LanguagePolicy("ku", "Kurdish", False),
)


class AudioProductionPlanner:
    def __init__(
        self,
        *,
        character_store: CharacterBibleStore,
        provider_registry: AudioProviderRegistry | None = None,
    ) -> None:
        self.character_store = character_store
        self.providers = provider_registry or default_audio_provider_registry()

    def validate_speaker(self, character_id: str) -> None:
        if self.character_store.get_profile(character_id) is None:
            raise UnknownSpeakerError(character_id)

    def make_localization_stub(
        self,
        *,
        line_id: str,
        episode_id: str,
        scene_id: str,
        speaker_character_id: str,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> LocalizedDialogue:
        self.validate_speaker(speaker_character_id)
        known = {policy.code for policy in DEFAULT_LANGUAGE_POLICIES}
        if target_language not in known:
            raise UnsupportedLanguageError(target_language)

        # This is intentionally a planning stub, not fake translation.
        localized = source_text if source_language == target_language else ""
        status = "source_ready" if localized else "translation_required"
        return LocalizedDialogue(
            line_id=line_id,
            episode_id=episode_id,
            scene_id=scene_id,
            speaker_character_id=speaker_character_id,
            source_language=source_language,
            target_language=target_language,
            source_text=source_text,
            localized_text=localized,
            localization_status=status,
        )

    def make_tts_job(
        self,
        dialogue: LocalizedDialogue,
        *,
        voice: VoiceProfile,
        allow_paid: bool,
        allow_external: bool,
        commercial_use: bool = True,
    ) -> AudioJob:
        self.validate_speaker(dialogue.speaker_character_id)

        if dialogue.localization_status != "source_ready" and not dialogue.localized_text.strip():
            raise AudioPipelineError(
                f"dialogue {dialogue.line_id} must be localized before TTS"
            )

        provider = self.providers.choose(
            language=dialogue.target_language,
            capability="tts",
            allow_paid=allow_paid,
            allow_external=allow_external,
            commercial_use=commercial_use,
            preferred=voice.provider_preference,
        )

        payload = {
            "text": dialogue.localized_text,
            "voice_id": voice.voice_id,
            "speaking_style": voice.speaking_style,
            "reference_audio_uri": voice.reference_audio_uri,
        }
        return AudioJob(
            job_id=f"tts:{dialogue.episode_id}:{dialogue.line_id}:{dialogue.target_language}",
            task_type=AudioTaskType.DIALOGUE_TTS,
            episode_id=dialogue.episode_id,
            scene_id=dialogue.scene_id,
            language=dialogue.target_language,
            speaker_character_id=dialogue.speaker_character_id,
            provider_id=provider.provider_id,
            payload=payload,
            paid=provider.paid,
            external=provider.external,
        )

    @staticmethod
    def make_music_cue(
        *,
        episode_id: str,
        scene_id: str,
        language: str,
        mood: str,
        duration_seconds: int,
    ) -> AudioJob:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        return AudioJob(
            job_id=f"music:{episode_id}:{scene_id}",
            task_type=AudioTaskType.MUSIC_CUE,
            episode_id=episode_id,
            scene_id=scene_id,
            language=language,
            speaker_character_id=None,
            provider_id=None,
            payload={
                "mood": mood,
                "duration_seconds": duration_seconds,
                "vocals_allowed": False,
                "child_safe_required": True,
            },
            paid=False,
            external=False,
        )


class AudioManifestStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_jobs (
                    job_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    provider_id TEXT,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_planned(self, job: AudioJob) -> None:
        payload = job.to_payload()
        digest = _hash(payload)
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audio_jobs (
                    job_id, episode_id, task_type, language, provider_id,
                    payload_hash, payload_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    provider_id=excluded.provider_id,
                    payload_hash=excluded.payload_hash,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    job.job_id,
                    job.episode_id,
                    job.task_type.value,
                    job.language,
                    job.provider_id,
                    digest,
                    _stable_json(payload),
                    now,
                    now,
                ),
            )

    def count(self, episode_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM audio_jobs WHERE episode_id=?",
                (episode_id,),
            ).fetchone()
        return int(row["c"])
