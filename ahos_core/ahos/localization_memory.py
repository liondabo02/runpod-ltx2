from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .audio_pipeline import (
    DEFAULT_LANGUAGE_POLICIES,
    LocalizedDialogue,
    UnsupportedLanguageError,
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


class LocalizationMemoryError(RuntimeError):
    pass


class TranslationNotApprovedError(LocalizationMemoryError):
    pass


class TerminologyViolationError(LocalizationMemoryError):
    pass


class TranslationStatus(str, Enum):
    TRANSLATION_REQUIRED = "translation_required"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    SOURCE_READY = "source_ready"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TerminologyRule:
    term_id: str
    source_text: str
    target_language: str
    approved_text: str
    pronunciation_hint: str
    locked: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class LocalizationVersion:
    localization_id: str
    episode_id: str
    scene_id: str
    line_id: str
    speaker_character_id: str
    source_language: str
    target_language: str
    source_text: str
    localized_text: str
    status: TranslationStatus
    reviewer: str
    version: int
    content_hash: str
    created_at: str


class LocalizationMemoryStore:
    """Versioned localization memory with terminology locks and approval gates."""

    def __init__(
        self,
        path: str | Path,
        *,
        character_store: CharacterBibleStore,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.character_store = character_store
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
                CREATE TABLE IF NOT EXISTS terminology_rules (
                    term_id TEXT PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    approved_text TEXT NOT NULL,
                    pronunciation_hint TEXT NOT NULL,
                    locked INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS localization_versions (
                    localization_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    episode_id TEXT NOT NULL,
                    scene_id TEXT NOT NULL,
                    line_id TEXT NOT NULL,
                    speaker_character_id TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    localized_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(localization_id, version)
                );

                CREATE INDEX IF NOT EXISTS idx_localization_current
                ON localization_versions(localization_id, version DESC);
                """
            )

    @staticmethod
    def _known_languages() -> set[str]:
        return {policy.code for policy in DEFAULT_LANGUAGE_POLICIES}

    def _validate_language(self, language: str) -> str:
        code = language.strip().lower()
        if code not in self._known_languages():
            raise UnsupportedLanguageError(code)
        return code

    def add_terminology(
        self,
        *,
        term_id: str,
        source_text: str,
        target_language: str,
        approved_text: str,
        pronunciation_hint: str = "",
        locked: bool = True,
    ) -> TerminologyRule:
        term_id = term_id.strip()
        source_text = source_text.strip()
        approved_text = approved_text.strip()
        target_language = self._validate_language(target_language)

        if not term_id or not source_text or not approved_text:
            raise ValueError(
                "term_id, source_text and approved_text must not be empty"
            )

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM terminology_rules WHERE term_id=?",
                (term_id,),
            ).fetchone()
            if existing is not None:
                same = (
                    str(existing["source_text"]) == source_text
                    and str(existing["target_language"]) == target_language
                    and str(existing["approved_text"]) == approved_text
                    and str(existing["pronunciation_hint"]) == pronunciation_hint
                )
                if bool(existing["locked"]) and not same:
                    raise TerminologyViolationError(
                        f"locked terminology rule {term_id} cannot be changed"
                    )
                return self._term_from_row(existing)

            created_at = _utc_now()
            conn.execute(
                """
                INSERT INTO terminology_rules (
                    term_id, source_text, target_language, approved_text,
                    pronunciation_hint, locked, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    term_id,
                    source_text,
                    target_language,
                    approved_text,
                    pronunciation_hint,
                    int(locked),
                    created_at,
                ),
            )

        return TerminologyRule(
            term_id=term_id,
            source_text=source_text,
            target_language=target_language,
            approved_text=approved_text,
            pronunciation_hint=pronunciation_hint,
            locked=locked,
            created_at=created_at,
        )

    @staticmethod
    def _term_from_row(row: sqlite3.Row) -> TerminologyRule:
        return TerminologyRule(
            term_id=str(row["term_id"]),
            source_text=str(row["source_text"]),
            target_language=str(row["target_language"]),
            approved_text=str(row["approved_text"]),
            pronunciation_hint=str(row["pronunciation_hint"]),
            locked=bool(row["locked"]),
            created_at=str(row["created_at"]),
        )

    def terminology(self, target_language: str) -> tuple[TerminologyRule, ...]:
        target_language = self._validate_language(target_language)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM terminology_rules
                WHERE target_language=?
                ORDER BY term_id
                """,
                (target_language,),
            ).fetchall()
        return tuple(self._term_from_row(row) for row in rows)

    @staticmethod
    def localization_id(
        *,
        episode_id: str,
        line_id: str,
        target_language: str,
    ) -> str:
        return f"{episode_id}:{line_id}:{target_language.lower()}"

    def _validate_speaker(self, character_id: str) -> None:
        if self.character_store.get_profile(character_id) is None:
            raise LocalizationMemoryError(f"unknown character: {character_id}")

    def _latest(self, localization_id: str) -> LocalizationVersion | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM localization_versions
                WHERE localization_id=?
                ORDER BY version DESC
                LIMIT 1
                """,
                (localization_id,),
            ).fetchone()
        return self._version_from_row(row) if row is not None else None

    @staticmethod
    def _version_from_row(row: sqlite3.Row) -> LocalizationVersion:
        return LocalizationVersion(
            localization_id=str(row["localization_id"]),
            episode_id=str(row["episode_id"]),
            scene_id=str(row["scene_id"]),
            line_id=str(row["line_id"]),
            speaker_character_id=str(row["speaker_character_id"]),
            source_language=str(row["source_language"]),
            target_language=str(row["target_language"]),
            source_text=str(row["source_text"]),
            localized_text=str(row["localized_text"]),
            status=TranslationStatus(str(row["status"])),
            reviewer=str(row["reviewer"]),
            version=int(row["version"]),
            content_hash=str(row["content_hash"]),
            created_at=str(row["created_at"]),
        )

    def _append(
        self,
        *,
        episode_id: str,
        scene_id: str,
        line_id: str,
        speaker_character_id: str,
        source_language: str,
        target_language: str,
        source_text: str,
        localized_text: str,
        status: TranslationStatus,
        reviewer: str,
    ) -> LocalizationVersion:
        self._validate_speaker(speaker_character_id)
        source_language = self._validate_language(source_language)
        target_language = self._validate_language(target_language)

        localization_id = self.localization_id(
            episode_id=episode_id,
            line_id=line_id,
            target_language=target_language,
        )
        current = self._latest(localization_id)
        version = 1 if current is None else current.version + 1
        payload = {
            "localization_id": localization_id,
            "episode_id": episode_id,
            "scene_id": scene_id,
            "line_id": line_id,
            "speaker_character_id": speaker_character_id,
            "source_language": source_language,
            "target_language": target_language,
            "source_text": source_text,
            "localized_text": localized_text,
            "status": status.value,
            "reviewer": reviewer,
        }
        digest = _hash(payload)
        created_at = _utc_now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO localization_versions (
                    localization_id, version, episode_id, scene_id, line_id,
                    speaker_character_id, source_language, target_language,
                    source_text, localized_text, status, reviewer,
                    content_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    localization_id,
                    version,
                    episode_id,
                    scene_id,
                    line_id,
                    speaker_character_id,
                    source_language,
                    target_language,
                    source_text,
                    localized_text,
                    status.value,
                    reviewer,
                    digest,
                    created_at,
                ),
            )

        return LocalizationVersion(
            localization_id=localization_id,
            episode_id=episode_id,
            scene_id=scene_id,
            line_id=line_id,
            speaker_character_id=speaker_character_id,
            source_language=source_language,
            target_language=target_language,
            source_text=source_text,
            localized_text=localized_text,
            status=status,
            reviewer=reviewer,
            version=version,
            content_hash=digest,
            created_at=created_at,
        )

    def create_required(
        self,
        *,
        episode_id: str,
        scene_id: str,
        line_id: str,
        speaker_character_id: str,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> LocalizationVersion:
        source_language = self._validate_language(source_language)
        target_language = self._validate_language(target_language)
        text = source_text.strip()
        if not text:
            raise ValueError("source_text must not be empty")

        if source_language == target_language:
            localized_text = text
            status = TranslationStatus.SOURCE_READY
        else:
            localized_text = ""
            status = TranslationStatus.TRANSLATION_REQUIRED

        return self._append(
            episode_id=episode_id,
            scene_id=scene_id,
            line_id=line_id,
            speaker_character_id=speaker_character_id,
            source_language=source_language,
            target_language=target_language,
            source_text=text,
            localized_text=localized_text,
            status=status,
            reviewer="",
        )

    def submit_translation(
        self,
        localization_id: str,
        *,
        localized_text: str,
        translator: str,
    ) -> LocalizationVersion:
        current = self._latest(localization_id)
        if current is None:
            raise LocalizationMemoryError(
                f"unknown localization: {localization_id}"
            )
        text = localized_text.strip()
        translator = translator.strip()
        if not text or not translator:
            raise ValueError("localized_text and translator must not be empty")

        return self._append(
            episode_id=current.episode_id,
            scene_id=current.scene_id,
            line_id=current.line_id,
            speaker_character_id=current.speaker_character_id,
            source_language=current.source_language,
            target_language=current.target_language,
            source_text=current.source_text,
            localized_text=text,
            status=TranslationStatus.REVIEW_REQUIRED,
            reviewer=translator,
        )

    def _validate_locked_terminology(self, item: LocalizationVersion) -> None:
        source_folded = item.source_text.casefold()
        localized_folded = item.localized_text.casefold()
        violations: list[str] = []

        for rule in self.terminology(item.target_language):
            if not rule.locked:
                continue
            if rule.source_text.casefold() in source_folded:
                if rule.approved_text.casefold() not in localized_folded:
                    violations.append(rule.term_id)

        if violations:
            raise TerminologyViolationError(
                "locked terminology missing from localization: "
                + ", ".join(sorted(violations))
            )

    def approve(
        self,
        localization_id: str,
        *,
        reviewer: str,
    ) -> LocalizationVersion:
        current = self._latest(localization_id)
        if current is None:
            raise LocalizationMemoryError(
                f"unknown localization: {localization_id}"
            )
        reviewer = reviewer.strip()
        if not reviewer:
            raise ValueError("reviewer must not be empty")
        if current.status not in {
            TranslationStatus.REVIEW_REQUIRED,
            TranslationStatus.SOURCE_READY,
        }:
            raise TranslationNotApprovedError(
                f"localization {localization_id} is not reviewable from "
                f"status={current.status.value}"
            )
        if not current.localized_text.strip():
            raise TranslationNotApprovedError(
                f"localization {localization_id} has no translated text"
            )

        self._validate_locked_terminology(current)

        return self._append(
            episode_id=current.episode_id,
            scene_id=current.scene_id,
            line_id=current.line_id,
            speaker_character_id=current.speaker_character_id,
            source_language=current.source_language,
            target_language=current.target_language,
            source_text=current.source_text,
            localized_text=current.localized_text,
            status=TranslationStatus.APPROVED,
            reviewer=reviewer,
        )

    def history(self, localization_id: str) -> tuple[LocalizationVersion, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM localization_versions
                WHERE localization_id=?
                ORDER BY version
                """,
                (localization_id,),
            ).fetchall()
        return tuple(self._version_from_row(row) for row in rows)

    def approved_dialogue(self, localization_id: str) -> LocalizedDialogue:
        current = self._latest(localization_id)
        if current is None or current.status not in {
            TranslationStatus.APPROVED,
            TranslationStatus.SOURCE_READY,
        }:
            raise TranslationNotApprovedError(
                f"localization {localization_id} is not approved for TTS"
            )
        return LocalizedDialogue(
            line_id=current.line_id,
            episode_id=current.episode_id,
            scene_id=current.scene_id,
            speaker_character_id=current.speaker_character_id,
            source_language=current.source_language,
            target_language=current.target_language,
            source_text=current.source_text,
            localized_text=current.localized_text,
            localization_status=current.status.value,
        )
