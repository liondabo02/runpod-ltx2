from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .audio_pipeline import (
    AudioJob,
    AudioProductionPlanner,
    AudioProviderRegistry,
    LocalizedDialogue,
    UnsupportedLanguageError,
    VoiceProfile,
    default_audio_provider_registry,
)
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


class VoiceContinuityError(RuntimeError):
    pass


class VoiceBindingMissingError(VoiceContinuityError):
    pass


class LockedVoiceBindingError(VoiceContinuityError):
    pass


@dataclass(frozen=True, slots=True)
class CharacterVoiceBinding:
    character_id: str
    language: str
    provider_id: str
    voice_id: str
    speaking_style: str
    reference_audio_uri: str | None
    version: int
    content_hash: str
    owner_override: bool
    created_at: str


class VoiceContinuityStore:
    """Persistent per-character/per-language voice identity memory.

    Voice identity never falls back to another language silently. Once a
    binding exists, changing the provider, voice ID, reference audio, or style
    requires an explicit owner override so recurring characters keep the same
    approved voice across episodes.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        character_store: CharacterBibleStore,
        provider_registry: AudioProviderRegistry | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.character_store = character_store
        self.providers = provider_registry or default_audio_provider_registry()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS voice_bindings (
                    character_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    provider_id TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    speaking_style TEXT NOT NULL,
                    reference_audio_uri TEXT,
                    content_hash TEXT NOT NULL,
                    owner_override INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(character_id, language, version)
                );

                CREATE INDEX IF NOT EXISTS idx_voice_bindings_current
                ON voice_bindings(character_id, language, version DESC);
                """
            )

    def _validate_character(self, character_id: str) -> None:
        if self.character_store.get_profile(character_id) is None:
            raise VoiceContinuityError(f"unknown character: {character_id}")

    def _validate_provider(self, *, provider_id: str, language: str) -> None:
        provider = next(
            (item for item in self.providers.list() if item.provider_id == provider_id),
            None,
        )
        if provider is None:
            raise VoiceContinuityError(f"unknown audio provider: {provider_id}")
        if language not in provider.supported_languages:
            raise UnsupportedLanguageError(
                f"provider {provider_id!r} does not support language {language!r}"
            )
        if "tts" not in provider.capabilities:
            raise VoiceContinuityError(
                f"provider {provider_id!r} does not provide TTS"
            )
        if not provider.commercial_default:
            raise VoiceContinuityError(
                f"provider {provider_id!r} is not approved for commercial default use"
            )

    @staticmethod
    def _payload(
        *,
        character_id: str,
        language: str,
        provider_id: str,
        voice_id: str,
        speaking_style: str,
        reference_audio_uri: str | None,
    ) -> dict[str, object]:
        return {
            "character_id": character_id,
            "language": language,
            "provider_id": provider_id,
            "voice_id": voice_id,
            "speaking_style": speaking_style,
            "reference_audio_uri": reference_audio_uri,
        }

    def bind(
        self,
        *,
        character_id: str,
        language: str,
        provider_id: str,
        voice_id: str,
        speaking_style: str = "age-appropriate, clear, warm",
        reference_audio_uri: str | None = None,
        owner_override: bool = False,
    ) -> CharacterVoiceBinding:
        character_id = character_id.strip()
        language = language.strip().lower()
        provider_id = provider_id.strip()
        voice_id = voice_id.strip()
        speaking_style = speaking_style.strip()

        if not all((character_id, language, provider_id, voice_id, speaking_style)):
            raise ValueError(
                "character_id, language, provider_id, voice_id and speaking_style "
                "must not be empty"
            )

        self._validate_character(character_id)
        self._validate_provider(provider_id=provider_id, language=language)

        payload = self._payload(
            character_id=character_id,
            language=language,
            provider_id=provider_id,
            voice_id=voice_id,
            speaking_style=speaking_style,
            reference_audio_uri=reference_audio_uri,
        )
        digest = _hash(payload)
        current = self.get(character_id, language)

        if current is not None:
            if current.content_hash == digest:
                return current
            if not owner_override:
                raise LockedVoiceBindingError(
                    f"voice binding for {character_id}/{language} is locked; "
                    "owner_override=True is required"
                )
            version = current.version + 1
        else:
            version = 1

        created_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO voice_bindings (
                    character_id, language, version, provider_id, voice_id,
                    speaking_style, reference_audio_uri, content_hash,
                    owner_override, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    character_id,
                    language,
                    version,
                    provider_id,
                    voice_id,
                    speaking_style,
                    reference_audio_uri,
                    digest,
                    int(owner_override),
                    created_at,
                ),
            )

        return CharacterVoiceBinding(
            character_id=character_id,
            language=language,
            provider_id=provider_id,
            voice_id=voice_id,
            speaking_style=speaking_style,
            reference_audio_uri=reference_audio_uri,
            version=version,
            content_hash=digest,
            owner_override=owner_override,
            created_at=created_at,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CharacterVoiceBinding:
        return CharacterVoiceBinding(
            character_id=str(row["character_id"]),
            language=str(row["language"]),
            provider_id=str(row["provider_id"]),
            voice_id=str(row["voice_id"]),
            speaking_style=str(row["speaking_style"]),
            reference_audio_uri=(
                str(row["reference_audio_uri"])
                if row["reference_audio_uri"] is not None
                else None
            ),
            version=int(row["version"]),
            content_hash=str(row["content_hash"]),
            owner_override=bool(row["owner_override"]),
            created_at=str(row["created_at"]),
        )

    def get(
        self,
        character_id: str,
        language: str,
    ) -> CharacterVoiceBinding | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM voice_bindings
                WHERE character_id=? AND language=?
                ORDER BY version DESC
                LIMIT 1
                """,
                (character_id, language.lower()),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def history(
        self,
        character_id: str,
        language: str,
    ) -> tuple[CharacterVoiceBinding, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM voice_bindings
                WHERE character_id=? AND language=?
                ORDER BY version
                """,
                (character_id, language.lower()),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def require(
        self,
        character_id: str,
        language: str,
    ) -> CharacterVoiceBinding:
        binding = self.get(character_id, language)
        if binding is None:
            raise VoiceBindingMissingError(
                f"no approved voice binding for {character_id}/{language}; "
                "wrong-language fallback is forbidden"
            )
        return binding

    def voice_profile(
        self,
        character_id: str,
        language: str,
    ) -> VoiceProfile:
        binding = self.require(character_id, language)
        return VoiceProfile(
            character_id=binding.character_id,
            voice_id=binding.voice_id,
            provider_preference=(binding.provider_id,),
            speaking_style=binding.speaking_style,
            reference_audio_uri=binding.reference_audio_uri,
        )

    def make_tts_job(
        self,
        dialogue: LocalizedDialogue,
        *,
        allow_paid: bool,
        allow_external: bool,
        commercial_use: bool = True,
    ) -> AudioJob:
        if dialogue.speaker_character_id is None:
            raise VoiceContinuityError("dialogue has no speaker")
        voice = self.voice_profile(
            dialogue.speaker_character_id,
            dialogue.target_language,
        )
        planner = AudioProductionPlanner(
            character_store=self.character_store,
            provider_registry=self.providers,
        )
        return planner.make_tts_job(
            dialogue,
            voice=voice,
            allow_paid=allow_paid,
            allow_external=allow_external,
            commercial_use=commercial_use,
        )
