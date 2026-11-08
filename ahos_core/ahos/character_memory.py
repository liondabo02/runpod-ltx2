from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


class CharacterMemoryError(RuntimeError):
    pass


class LockedCharacterFieldError(CharacterMemoryError):
    pass


class ContinuityReferenceError(CharacterMemoryError):
    pass


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    character_id: str
    display_name: str
    canonical_role: str
    family_group: str = ""
    age_stage: str = ""
    visual_anchors: tuple[str, ...] = ()
    personality_anchors: tuple[str, ...] = ()
    voice_anchors: tuple[str, ...] = ()
    continuity_rules: tuple[str, ...] = ()
    locked_fields: frozenset[str] = frozenset(
        {"display_name", "canonical_role", "family_group"}
    )

    def __post_init__(self) -> None:
        for field_name in ("character_id", "display_name", "canonical_role"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} must not be empty")

        valid_lock_fields = {
            "display_name",
            "canonical_role",
            "family_group",
            "age_stage",
            "visual_anchors",
            "personality_anchors",
            "voice_anchors",
            "continuity_rules",
        }
        unknown = set(self.locked_fields) - valid_lock_fields
        if unknown:
            raise ValueError(f"unknown locked_fields: {sorted(unknown)}")

    def to_payload(self) -> dict[str, object]:
        return {
            "character_id": self.character_id,
            "display_name": self.display_name,
            "canonical_role": self.canonical_role,
            "family_group": self.family_group,
            "age_stage": self.age_stage,
            "visual_anchors": list(self.visual_anchors),
            "personality_anchors": list(self.personality_anchors),
            "voice_anchors": list(self.voice_anchors),
            "continuity_rules": list(self.continuity_rules),
            "locked_fields": sorted(self.locked_fields),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CharacterProfile":
        return cls(
            character_id=str(payload["character_id"]),
            display_name=str(payload["display_name"]),
            canonical_role=str(payload["canonical_role"]),
            family_group=str(payload.get("family_group") or ""),
            age_stage=str(payload.get("age_stage") or ""),
            visual_anchors=tuple(str(x) for x in payload.get("visual_anchors", ())),
            personality_anchors=tuple(
                str(x) for x in payload.get("personality_anchors", ())
            ),
            voice_anchors=tuple(str(x) for x in payload.get("voice_anchors", ())),
            continuity_rules=tuple(
                str(x) for x in payload.get("continuity_rules", ())
            ),
            locked_fields=frozenset(
                str(x) for x in payload.get("locked_fields", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class CharacterVersion:
    character_id: str
    version: int
    content_hash: str
    created_at: str
    author: str
    reason: str
    owner_override: bool
    profile: CharacterProfile


@dataclass(frozen=True, slots=True)
class CharacterRelationship:
    relationship_id: str
    from_character_id: str
    to_character_id: str
    relationship_type: str
    notes: str = ""
    locked: bool = True


@dataclass(frozen=True, slots=True)
class CanonFact:
    fact_id: str
    scope_type: str
    scope_id: str
    fact_key: str
    fact_value: object
    locked: bool
    first_seen_episode: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class EpisodeContinuityEvent:
    event_id: str
    episode_id: str
    sequence_no: int
    event_type: str
    payload: dict[str, object]
    created_at: str


class CharacterBibleStore:
    """Versioned, local-only character and continuity memory.

    The store performs no AI, network, publishing, messaging, payment,
    deployment, credential, or external-service action.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS characters (
                    character_id TEXT PRIMARY KEY,
                    current_version INTEGER NOT NULL,
                    current_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS character_versions (
                    character_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    author TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    owner_override INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(character_id, version),
                    FOREIGN KEY(character_id) REFERENCES characters(character_id)
                );

                CREATE TABLE IF NOT EXISTS relationships (
                    relationship_id TEXT PRIMARY KEY,
                    from_character_id TEXT NOT NULL,
                    to_character_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    locked INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(from_character_id) REFERENCES characters(character_id),
                    FOREIGN KEY(to_character_id) REFERENCES characters(character_id)
                );

                CREATE TABLE IF NOT EXISTS canon_facts (
                    fact_id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value_json TEXT NOT NULL,
                    locked INTEGER NOT NULL,
                    first_seen_episode TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS episode_events (
                    event_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(episode_id, sequence_no)
                );

                CREATE INDEX IF NOT EXISTS idx_character_versions
                    ON character_versions(character_id, version);
                CREATE INDEX IF NOT EXISTS idx_relationship_from
                    ON relationships(from_character_id);
                CREATE INDEX IF NOT EXISTS idx_relationship_to
                    ON relationships(to_character_id);
                CREATE INDEX IF NOT EXISTS idx_episode_events
                    ON episode_events(episode_id, sequence_no);
                """
            )

    def character_ids(self) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT character_id FROM characters ORDER BY character_id"
            ).fetchall()
        return tuple(str(row["character_id"]) for row in rows)

    def get_profile(self, character_id: str) -> CharacterProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM character_versions
                WHERE character_id=?
                ORDER BY version DESC
                LIMIT 1
                """,
                (character_id,),
            ).fetchone()
        if row is None:
            return None
        return CharacterProfile.from_payload(json.loads(row["payload_json"]))

    def version_history(self, character_id: str) -> tuple[CharacterVersion, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM character_versions
                WHERE character_id=?
                ORDER BY version ASC
                """,
                (character_id,),
            ).fetchall()

        result: list[CharacterVersion] = []
        for row in rows:
            result.append(
                CharacterVersion(
                    character_id=str(row["character_id"]),
                    version=int(row["version"]),
                    content_hash=str(row["content_hash"]),
                    created_at=str(row["created_at"]),
                    author=str(row["author"]),
                    reason=str(row["reason"]),
                    owner_override=bool(row["owner_override"]),
                    profile=CharacterProfile.from_payload(
                        json.loads(row["payload_json"])
                    ),
                )
            )
        return tuple(result)

    def upsert_profile(
        self,
        profile: CharacterProfile,
        *,
        author: str,
        reason: str,
        owner_override: bool = False,
    ) -> CharacterVersion:
        author = author.strip()
        reason = reason.strip()
        if not author:
            raise ValueError("author must not be empty")
        if not reason:
            raise ValueError("reason must not be empty")

        previous = self.get_profile(profile.character_id)
        if previous is not None:
            changed_locked = []
            previous_payload = previous.to_payload()
            next_payload = profile.to_payload()
            for field_name in previous.locked_fields:
                if previous_payload.get(field_name) != next_payload.get(field_name):
                    changed_locked.append(field_name)

            if changed_locked and not owner_override:
                raise LockedCharacterFieldError(
                    "locked character fields changed without owner override: "
                    + ", ".join(sorted(changed_locked))
                )

        payload = profile.to_payload()
        content_hash = _sha256(payload)
        now = _utc_now()

        with self._connect() as conn:
            current = conn.execute(
                "SELECT current_version, current_hash FROM characters WHERE character_id=?",
                (profile.character_id,),
            ).fetchone()

            if current is not None and str(current["current_hash"]) == content_hash:
                row = conn.execute(
                    """
                    SELECT *
                    FROM character_versions
                    WHERE character_id=? AND version=?
                    """,
                    (profile.character_id, int(current["current_version"])),
                ).fetchone()
                assert row is not None
                return CharacterVersion(
                    character_id=profile.character_id,
                    version=int(row["version"]),
                    content_hash=str(row["content_hash"]),
                    created_at=str(row["created_at"]),
                    author=str(row["author"]),
                    reason=str(row["reason"]),
                    owner_override=bool(row["owner_override"]),
                    profile=CharacterProfile.from_payload(
                        json.loads(row["payload_json"])
                    ),
                )

            next_version = 1 if current is None else int(current["current_version"]) + 1
            if current is None:
                conn.execute(
                    """
                    INSERT INTO characters (
                        character_id, current_version, current_hash,
                        display_name, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.character_id,
                        next_version,
                        content_hash,
                        profile.display_name,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE characters
                    SET current_version=?, current_hash=?, display_name=?, updated_at=?
                    WHERE character_id=?
                    """,
                    (
                        next_version,
                        content_hash,
                        profile.display_name,
                        now,
                        profile.character_id,
                    ),
                )

            conn.execute(
                """
                INSERT INTO character_versions (
                    character_id, version, content_hash, payload_json,
                    created_at, author, reason, owner_override
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.character_id,
                    next_version,
                    content_hash,
                    _stable_json(payload),
                    now,
                    author,
                    reason,
                    int(owner_override),
                ),
            )

        return self.version_history(profile.character_id)[-1]

    def add_relationship(
        self,
        relationship: CharacterRelationship,
    ) -> CharacterRelationship:
        if self.get_profile(relationship.from_character_id) is None:
            raise ContinuityReferenceError(
                f"unknown from_character_id: {relationship.from_character_id}"
            )
        if self.get_profile(relationship.to_character_id) is None:
            raise ContinuityReferenceError(
                f"unknown to_character_id: {relationship.to_character_id}"
            )
        if relationship.from_character_id == relationship.to_character_id:
            raise ContinuityReferenceError("self-relationship is not allowed")

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM relationships WHERE relationship_id=?",
                (relationship.relationship_id,),
            ).fetchone()
            if existing is not None:
                return self._relationship_from_row(existing)

            conn.execute(
                """
                INSERT INTO relationships (
                    relationship_id, from_character_id, to_character_id,
                    relationship_type, notes, locked, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship.relationship_id,
                    relationship.from_character_id,
                    relationship.to_character_id,
                    relationship.relationship_type,
                    relationship.notes,
                    int(relationship.locked),
                    _utc_now(),
                ),
            )
        return relationship

    def relationships(self) -> tuple[CharacterRelationship, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM relationships ORDER BY relationship_id"
            ).fetchall()
        return tuple(self._relationship_from_row(row) for row in rows)

    @staticmethod
    def _relationship_from_row(row: sqlite3.Row) -> CharacterRelationship:
        return CharacterRelationship(
            relationship_id=str(row["relationship_id"]),
            from_character_id=str(row["from_character_id"]),
            to_character_id=str(row["to_character_id"]),
            relationship_type=str(row["relationship_type"]),
            notes=str(row["notes"]),
            locked=bool(row["locked"]),
        )

    def add_canon_fact(
        self,
        *,
        fact_id: str,
        scope_type: str,
        scope_id: str,
        fact_key: str,
        fact_value: object,
        locked: bool = True,
        first_seen_episode: str | None = None,
    ) -> CanonFact:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM canon_facts WHERE fact_id=?",
                (fact_id,),
            ).fetchone()
            if existing is not None:
                old_value = json.loads(existing["fact_value_json"])
                if bool(existing["locked"]) and old_value != fact_value:
                    raise LockedCharacterFieldError(
                        f"locked canon fact {fact_id} cannot be changed"
                    )
                return self._canon_from_row(existing)

            conn.execute(
                """
                INSERT INTO canon_facts (
                    fact_id, scope_type, scope_id, fact_key,
                    fact_value_json, locked, first_seen_episode, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    scope_type,
                    scope_id,
                    fact_key,
                    _stable_json(fact_value),
                    int(locked),
                    first_seen_episode,
                    _utc_now(),
                ),
            )
        return CanonFact(
            fact_id=fact_id,
            scope_type=scope_type,
            scope_id=scope_id,
            fact_key=fact_key,
            fact_value=fact_value,
            locked=locked,
            first_seen_episode=first_seen_episode,
            created_at=_utc_now(),
        )

    @staticmethod
    def _canon_from_row(row: sqlite3.Row) -> CanonFact:
        return CanonFact(
            fact_id=str(row["fact_id"]),
            scope_type=str(row["scope_type"]),
            scope_id=str(row["scope_id"]),
            fact_key=str(row["fact_key"]),
            fact_value=json.loads(row["fact_value_json"]),
            locked=bool(row["locked"]),
            first_seen_episode=(
                str(row["first_seen_episode"])
                if row["first_seen_episode"] is not None
                else None
            ),
            created_at=str(row["created_at"]),
        )

    def canon_facts(self) -> tuple[CanonFact, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM canon_facts ORDER BY fact_id"
            ).fetchall()
        return tuple(self._canon_from_row(row) for row in rows)

    def record_episode_event(
        self,
        *,
        event_id: str,
        episode_id: str,
        sequence_no: int,
        event_type: str,
        payload: Mapping[str, object],
    ) -> EpisodeContinuityEvent:
        if sequence_no < 1:
            raise ValueError("sequence_no must be >= 1")
        if not episode_id.strip():
            raise ValueError("episode_id must not be empty")
        if not event_type.strip():
            raise ValueError("event_type must not be empty")

        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO episode_events (
                    event_id, episode_id, sequence_no, event_type,
                    payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    episode_id,
                    sequence_no,
                    event_type,
                    _stable_json(dict(payload)),
                    now,
                ),
            )
        return EpisodeContinuityEvent(
            event_id=event_id,
            episode_id=episode_id,
            sequence_no=sequence_no,
            event_type=event_type,
            payload=dict(payload),
            created_at=now,
        )

    def episode_events(
        self,
        episode_id: str | None = None,
    ) -> tuple[EpisodeContinuityEvent, ...]:
        with self._connect() as conn:
            if episode_id is None:
                rows = conn.execute(
                    """
                    SELECT * FROM episode_events
                    ORDER BY created_at, episode_id, sequence_no
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM episode_events
                    WHERE episode_id=?
                    ORDER BY sequence_no
                    """,
                    (episode_id,),
                ).fetchall()

        return tuple(
            EpisodeContinuityEvent(
                event_id=str(row["event_id"]),
                episode_id=str(row["episode_id"]),
                sequence_no=int(row["sequence_no"]),
                event_type=str(row["event_type"]),
                payload=json.loads(row["payload_json"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        )

    def validate_reference_integrity(self) -> None:
        known = set(self.character_ids())
        errors: list[str] = []

        for rel in self.relationships():
            if rel.from_character_id not in known:
                errors.append(
                    f"{rel.relationship_id} unknown source {rel.from_character_id}"
                )
            if rel.to_character_id not in known:
                errors.append(
                    f"{rel.relationship_id} unknown target {rel.to_character_id}"
                )

        if errors:
            raise ContinuityReferenceError("; ".join(errors))

    def snapshot(self) -> dict[str, object]:
        profiles = []
        for character_id in self.character_ids():
            profile = self.get_profile(character_id)
            assert profile is not None
            versions = self.version_history(character_id)
            profiles.append(
                {
                    **profile.to_payload(),
                    "current_version": versions[-1].version,
                    "content_hash": versions[-1].content_hash,
                }
            )

        return {
            "schema": "ahos.character-bible.v1",
            "generated_at": _utc_now(),
            "characters": profiles,
            "relationships": [
                {
                    "relationship_id": r.relationship_id,
                    "from_character_id": r.from_character_id,
                    "to_character_id": r.to_character_id,
                    "relationship_type": r.relationship_type,
                    "notes": r.notes,
                    "locked": r.locked,
                }
                for r in self.relationships()
            ],
            "canon_facts": [
                {
                    "fact_id": f.fact_id,
                    "scope_type": f.scope_type,
                    "scope_id": f.scope_id,
                    "fact_key": f.fact_key,
                    "fact_value": f.fact_value,
                    "locked": f.locked,
                    "first_seen_episode": f.first_seen_episode,
                }
                for f in self.canon_facts()
            ],
            "episode_events": [
                {
                    "event_id": e.event_id,
                    "episode_id": e.episode_id,
                    "sequence_no": e.sequence_no,
                    "event_type": e.event_type,
                    "payload": e.payload,
                    "created_at": e.created_at,
                }
                for e in self.episode_events()
            ],
        }

    def export_snapshot(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                self.snapshot(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return destination


def load_seed(
    store: CharacterBibleStore,
    seed: Mapping[str, object],
    *,
    author: str = "owner-seed",
) -> None:
    for raw in seed.get("characters", []):
        profile = CharacterProfile.from_payload(raw)
        store.upsert_profile(
            profile,
            author=author,
            reason="initial character bible seed",
        )

    for raw in seed.get("relationships", []):
        store.add_relationship(
            CharacterRelationship(
                relationship_id=str(raw["relationship_id"]),
                from_character_id=str(raw["from_character_id"]),
                to_character_id=str(raw["to_character_id"]),
                relationship_type=str(raw["relationship_type"]),
                notes=str(raw.get("notes") or ""),
                locked=bool(raw.get("locked", True)),
            )
        )

    for raw in seed.get("canon_facts", []):
        store.add_canon_fact(
            fact_id=str(raw["fact_id"]),
            scope_type=str(raw["scope_type"]),
            scope_id=str(raw["scope_id"]),
            fact_key=str(raw["fact_key"]),
            fact_value=raw["fact_value"],
            locked=bool(raw.get("locked", True)),
            first_seen_episode=(
                str(raw["first_seen_episode"])
                if raw.get("first_seen_episode")
                else None
            ),
        )

    store.validate_reference_integrity()
