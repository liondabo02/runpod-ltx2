from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .character_memory import CharacterBibleStore
from .voice_continuity import CharacterVoiceBinding, VoiceContinuityStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VoiceEnrollmentError(RuntimeError):
    pass


class VoiceEnrollmentApprovalError(VoiceEnrollmentError):
    pass


class VoiceReferenceRightsError(VoiceEnrollmentError):
    pass


@dataclass(frozen=True, slots=True)
class VoiceEnrollment:
    enrollment_id: str
    character_id: str
    language: str
    provider_id: str
    voice_id: str
    speaking_style: str
    reference_audio_uri: str
    reference_sha256: str
    reference_origin: str
    rights_confirmed: bool
    speaker_consent_confirmed: bool
    human_similarity_approved: bool
    owner_approved: bool
    version: int
    created_at: str


class VoiceEnrollmentStore:
    """Canonical voice enrollment gate for recurring characters.

    A reference voice cannot become canonical merely because a model can clone
    it. Enrollment requires provenance plus human/owner approval. For references
    derived from a real identifiable speaker, explicit rights and speaker
    consent are mandatory. Synthetic studio-owned references do not require
    speaker consent but still require rights and owner approval.
    """

    VALID_ORIGINS = frozenset({"synthetic", "recorded-human"})

    def __init__(
        self,
        path: str | Path,
        *,
        character_store: CharacterBibleStore,
        voice_store: VoiceContinuityStore,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.character_store = character_store
        self.voice_store = voice_store
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
                CREATE TABLE IF NOT EXISTS voice_enrollments (
                    enrollment_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    character_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    speaking_style TEXT NOT NULL,
                    reference_audio_uri TEXT NOT NULL,
                    reference_sha256 TEXT NOT NULL,
                    reference_origin TEXT NOT NULL,
                    rights_confirmed INTEGER NOT NULL,
                    speaker_consent_confirmed INTEGER NOT NULL,
                    human_similarity_approved INTEGER NOT NULL,
                    owner_approved INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(enrollment_id, version)
                );

                CREATE INDEX IF NOT EXISTS idx_voice_enrollment_current
                ON voice_enrollments(enrollment_id, version DESC);
                """
            )

    @staticmethod
    def enrollment_id(character_id: str, language: str) -> str:
        return f"{character_id.strip()}:{language.strip().lower()}"

    def _latest(self, enrollment_id: str) -> VoiceEnrollment | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM voice_enrollments
                WHERE enrollment_id=?
                ORDER BY version DESC
                LIMIT 1
                """,
                (enrollment_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> VoiceEnrollment:
        return VoiceEnrollment(
            enrollment_id=str(row["enrollment_id"]),
            character_id=str(row["character_id"]),
            language=str(row["language"]),
            provider_id=str(row["provider_id"]),
            voice_id=str(row["voice_id"]),
            speaking_style=str(row["speaking_style"]),
            reference_audio_uri=str(row["reference_audio_uri"]),
            reference_sha256=str(row["reference_sha256"]),
            reference_origin=str(row["reference_origin"]),
            rights_confirmed=bool(row["rights_confirmed"]),
            speaker_consent_confirmed=bool(row["speaker_consent_confirmed"]),
            human_similarity_approved=bool(row["human_similarity_approved"]),
            owner_approved=bool(row["owner_approved"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def sha256_file(path: str | Path) -> str:
        p = Path(path)
        digest = hashlib.sha256()
        with p.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def enroll(
        self,
        *,
        character_id: str,
        language: str,
        provider_id: str,
        voice_id: str,
        speaking_style: str,
        reference_audio_uri: str,
        reference_sha256: str,
        reference_origin: str,
        rights_confirmed: bool,
        speaker_consent_confirmed: bool,
        human_similarity_approved: bool,
        owner_approved: bool,
    ) -> tuple[VoiceEnrollment, CharacterVoiceBinding]:
        character_id = character_id.strip()
        language = language.strip().lower()
        provider_id = provider_id.strip()
        voice_id = voice_id.strip()
        speaking_style = speaking_style.strip()
        reference_audio_uri = reference_audio_uri.strip()
        reference_sha256 = reference_sha256.strip().lower()
        reference_origin = reference_origin.strip().lower()

        if self.character_store.get_profile(character_id) is None:
            raise VoiceEnrollmentError(f"unknown character: {character_id}")
        if reference_origin not in self.VALID_ORIGINS:
            raise VoiceEnrollmentError(
                f"reference_origin must be one of {sorted(self.VALID_ORIGINS)}"
            )
        if len(reference_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in reference_sha256
        ):
            raise VoiceEnrollmentError("reference_sha256 must be a SHA-256 hex digest")
        if not rights_confirmed:
            raise VoiceReferenceRightsError(
                "voice reference rights must be confirmed before enrollment"
            )
        if reference_origin == "recorded-human" and not speaker_consent_confirmed:
            raise VoiceReferenceRightsError(
                "recorded-human references require explicit speaker consent"
            )
        if not human_similarity_approved:
            raise VoiceEnrollmentApprovalError(
                "human speaker-similarity approval is required"
            )
        if not owner_approved:
            raise VoiceEnrollmentApprovalError(
                "owner approval is required for canonical voice enrollment"
            )

        enrollment_id = self.enrollment_id(character_id, language)
        current = self._latest(enrollment_id)
        version = 1 if current is None else current.version + 1
        created_at = _utc_now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO voice_enrollments (
                    enrollment_id, version, character_id, language,
                    provider_id, voice_id, speaking_style,
                    reference_audio_uri, reference_sha256, reference_origin,
                    rights_confirmed, speaker_consent_confirmed,
                    human_similarity_approved, owner_approved, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    enrollment_id,
                    version,
                    character_id,
                    language,
                    provider_id,
                    voice_id,
                    speaking_style,
                    reference_audio_uri,
                    reference_sha256,
                    reference_origin,
                    int(rights_confirmed),
                    int(speaker_consent_confirmed),
                    int(human_similarity_approved),
                    int(owner_approved),
                    created_at,
                ),
            )

        binding = self.voice_store.bind(
            character_id=character_id,
            language=language,
            provider_id=provider_id,
            voice_id=voice_id,
            speaking_style=speaking_style,
            reference_audio_uri=reference_audio_uri,
            owner_override=current is not None,
        )

        return (
            VoiceEnrollment(
                enrollment_id=enrollment_id,
                character_id=character_id,
                language=language,
                provider_id=provider_id,
                voice_id=voice_id,
                speaking_style=speaking_style,
                reference_audio_uri=reference_audio_uri,
                reference_sha256=reference_sha256,
                reference_origin=reference_origin,
                rights_confirmed=rights_confirmed,
                speaker_consent_confirmed=speaker_consent_confirmed,
                human_similarity_approved=human_similarity_approved,
                owner_approved=owner_approved,
                version=version,
                created_at=created_at,
            ),
            binding,
        )

    def get(self, character_id: str, language: str) -> VoiceEnrollment | None:
        return self._latest(self.enrollment_id(character_id, language))

    def history(
        self,
        character_id: str,
        language: str,
    ) -> tuple[VoiceEnrollment, ...]:
        enrollment_id = self.enrollment_id(character_id, language)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM voice_enrollments
                WHERE enrollment_id=?
                ORDER BY version
                """,
                (enrollment_id,),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)
