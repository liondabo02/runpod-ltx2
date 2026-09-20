from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from .character_memory import CharacterBibleStore, ContinuityReferenceError


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


class StoryPlanningError(RuntimeError):
    pass


class UnknownStoryCharacterError(StoryPlanningError):
    pass


class InvalidStoryPlanError(StoryPlanningError):
    pass


class EpisodeStatus(str, Enum):
    DRAFT = "draft"
    READY_FOR_OWNER_REVIEW = "ready_for_owner_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class EpisodeRequest:
    season_number: int
    episode_number: int
    topic: str
    learning_goal: str
    cast_ids: tuple[str, ...]
    target_duration_seconds: int = 480
    age_band: str = "young children"
    primary_language: str = "tr"
    child_safe_required: bool = True

    def __post_init__(self) -> None:
        if self.season_number < 1:
            raise ValueError("season_number must be >= 1")
        if self.episode_number < 1:
            raise ValueError("episode_number must be >= 1")
        if not self.topic.strip():
            raise ValueError("topic must not be empty")
        if not self.learning_goal.strip():
            raise ValueError("learning_goal must not be empty")
        if not self.cast_ids:
            raise ValueError("cast_ids must not be empty")
        if len(set(self.cast_ids)) != len(self.cast_ids):
            raise ValueError("cast_ids must be unique")
        if not 180 <= self.target_duration_seconds <= 1200:
            raise ValueError("target_duration_seconds must be between 180 and 1200")
        if not self.primary_language.strip():
            raise ValueError("primary_language must not be empty")

    @property
    def episode_id(self) -> str:
        return f"S{self.season_number:02d}E{self.episode_number:03d}"


@dataclass(frozen=True, slots=True)
class StoryCharacterContext:
    character_id: str
    display_name: str
    canonical_role: str
    age_stage: str
    personality_anchors: tuple[str, ...]
    continuity_rules: tuple[str, ...]
    related_character_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoryContext:
    episode_id: str
    characters: tuple[StoryCharacterContext, ...]
    canon_facts: tuple[dict[str, object], ...]
    recent_continuity_events: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class StoryBeat:
    beat_id: str
    purpose: str
    summary: str
    emotional_value: str
    learning_value: str


@dataclass(frozen=True, slots=True)
class DialogueLine:
    speaker_character_id: str
    text: str
    intent: str = ""


@dataclass(frozen=True, slots=True)
class SceneDraft:
    scene_id: str
    title: str
    setting: str
    cast_ids: tuple[str, ...]
    duration_seconds: int
    objective: str
    action_summary: str
    dialogue: tuple[DialogueLine, ...]


@dataclass(frozen=True, slots=True)
class EpisodeProductionPacket:
    episode_id: str
    season_number: int
    episode_number: int
    title: str
    logline: str
    topic: str
    learning_goal: str
    age_band: str
    primary_language: str
    target_duration_seconds: int
    child_safe_required: bool
    cast_ids: tuple[str, ...]
    continuity_notes: tuple[str, ...]
    beats: tuple[StoryBeat, ...]
    scenes: tuple[SceneDraft, ...]
    owner_approved: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "title": self.title,
            "logline": self.logline,
            "topic": self.topic,
            "learning_goal": self.learning_goal,
            "age_band": self.age_band,
            "primary_language": self.primary_language,
            "target_duration_seconds": self.target_duration_seconds,
            "child_safe_required": self.child_safe_required,
            "cast_ids": list(self.cast_ids),
            "continuity_notes": list(self.continuity_notes),
            "beats": [
                {
                    "beat_id": beat.beat_id,
                    "purpose": beat.purpose,
                    "summary": beat.summary,
                    "emotional_value": beat.emotional_value,
                    "learning_value": beat.learning_value,
                }
                for beat in self.beats
            ],
            "scenes": [
                {
                    "scene_id": scene.scene_id,
                    "title": scene.title,
                    "setting": scene.setting,
                    "cast_ids": list(scene.cast_ids),
                    "duration_seconds": scene.duration_seconds,
                    "objective": scene.objective,
                    "action_summary": scene.action_summary,
                    "dialogue": [
                        {
                            "speaker_character_id": line.speaker_character_id,
                            "text": line.text,
                            "intent": line.intent,
                        }
                        for line in scene.dialogue
                    ],
                }
                for scene in self.scenes
            ],
            "owner_approved": self.owner_approved,
        }


@dataclass(frozen=True, slots=True)
class EpisodeVersion:
    episode_id: str
    version: int
    content_hash: str
    status: EpisodeStatus
    created_at: str
    created_by: str
    reason: str
    owner_decision_at: str | None
    packet: EpisodeProductionPacket


class StoryPlanner(Protocol):
    def plan(
        self,
        request: EpisodeRequest,
        context: StoryContext,
    ) -> EpisodeProductionPacket:
        ...


class DeterministicLocalStoryPlanner:
    """Zero-cost reference planner used for validation and offline fallback."""

    def plan(
        self,
        request: EpisodeRequest,
        context: StoryContext,
    ) -> EpisodeProductionPacket:
        cast = tuple(item.character_id for item in context.characters)
        display = {item.character_id: item.display_name for item in context.characters}
        lead_a = cast[0]
        lead_b = cast[1] if len(cast) > 1 else cast[0]

        beats = (
            StoryBeat(
                "B01",
                "setup",
                f"{display[lead_a]} and {display[lead_b]} encounter the episode topic.",
                "curiosity",
                request.learning_goal,
            ),
            StoryBeat(
                "B02",
                "challenge",
                "A simple child-safe problem makes the learning goal meaningful.",
                "mild tension",
                request.learning_goal,
            ),
            StoryBeat(
                "B03",
                "attempt",
                "The children try a first solution and learn from the result.",
                "effort",
                request.learning_goal,
            ),
            StoryBeat(
                "B04",
                "resolution",
                "The cast resolves the problem together.",
                "relief",
                request.learning_goal,
            ),
            StoryBeat(
                "B05",
                "lesson",
                "The episode closes by naturally reinforcing the lesson.",
                "warmth",
                request.learning_goal,
            ),
        )

        scene_count = 5
        base = request.target_duration_seconds // scene_count
        durations = [base] * scene_count
        durations[-1] += request.target_duration_seconds - sum(durations)

        scenes = tuple(
            SceneDraft(
                scene_id=f"SCENE-{index:02d}",
                title=title,
                setting="approved recurring family/studio location",
                cast_ids=cast,
                duration_seconds=durations[index - 1],
                objective=objective,
                action_summary=summary,
                dialogue=(
                    DialogueLine(
                        lead_a,
                        f"{display[lead_a]} reacts to the situation in an age-appropriate way.",
                        "move story forward",
                    ),
                    DialogueLine(
                        lead_b,
                        f"{display[lead_b]} responds and supports the shared learning goal.",
                        "reinforce relationship",
                    ),
                ),
            )
            for index, (title, objective, summary) in enumerate(
                (
                    ("Opening", "introduce topic", beats[0].summary),
                    ("Challenge", "make problem clear", beats[1].summary),
                    ("First Try", "show learning through action", beats[2].summary),
                    ("Resolution", "resolve safely", beats[3].summary),
                    ("Warm Close", "land the lesson", beats[4].summary),
                ),
                start=1,
            )
        )

        continuity_notes = tuple(
            rule
            for character in context.characters
            for rule in character.continuity_rules
        )

        return EpisodeProductionPacket(
            episode_id=request.episode_id,
            season_number=request.season_number,
            episode_number=request.episode_number,
            title=f"{request.topic.strip()} - {request.episode_id}",
            logline=(
                f"A child-safe story about {request.topic.strip()} that reinforces "
                f"{request.learning_goal.strip()}."
            ),
            topic=request.topic.strip(),
            learning_goal=request.learning_goal.strip(),
            age_band=request.age_band.strip(),
            primary_language=request.primary_language.strip(),
            target_duration_seconds=request.target_duration_seconds,
            child_safe_required=request.child_safe_required,
            cast_ids=cast,
            continuity_notes=continuity_notes,
            beats=beats,
            scenes=scenes,
            owner_approved=False,
        )


class StructuredJsonStoryPlanner:
    """Adapter contract for a future AI story generator.

    The injected generator receives a strict prompt and must return one JSON
    object. The adapter itself does not perform network or AI calls.
    """

    def __init__(self, generator: Callable[[str], str]) -> None:
        self._generator = generator

    def plan(
        self,
        request: EpisodeRequest,
        context: StoryContext,
    ) -> EpisodeProductionPacket:
        prompt = {
            "contract": "ahos.story-plan.v1",
            "instruction": (
                "Return JSON only. Use only allowed character_ids. "
                "Do not add owner approval. Keep content child-safe. "
                "All scene durations must sum to target_duration_seconds."
            ),
            "request": {
                "episode_id": request.episode_id,
                "topic": request.topic,
                "learning_goal": request.learning_goal,
                "target_duration_seconds": request.target_duration_seconds,
                "age_band": request.age_band,
                "primary_language": request.primary_language,
                "allowed_character_ids": list(request.cast_ids),
            },
            "character_context": [
                {
                    "character_id": c.character_id,
                    "display_name": c.display_name,
                    "canonical_role": c.canonical_role,
                    "age_stage": c.age_stage,
                    "personality_anchors": list(c.personality_anchors),
                    "continuity_rules": list(c.continuity_rules),
                    "related_character_ids": list(c.related_character_ids),
                }
                for c in context.characters
            ],
            "canon_facts": list(context.canon_facts),
            "recent_continuity_events": list(context.recent_continuity_events),
        }

        raw = self._generator(
            "AHOS_STORY_PLANNER_INPUT\n" + json.dumps(
                prompt,
                ensure_ascii=False,
                indent=2,
            )
        )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidStoryPlanError(f"story planner returned invalid JSON: {exc}") from exc

        return _packet_from_mapping(payload, request)


def _packet_from_mapping(
    payload: Mapping[str, object],
    request: EpisodeRequest,
) -> EpisodeProductionPacket:
    beats = tuple(
        StoryBeat(
            beat_id=str(item["beat_id"]),
            purpose=str(item["purpose"]),
            summary=str(item["summary"]),
            emotional_value=str(item.get("emotional_value") or ""),
            learning_value=str(item.get("learning_value") or ""),
        )
        for item in payload.get("beats", ())
    )

    scenes = []
    for raw_scene in payload.get("scenes", ()):
        dialogue = tuple(
            DialogueLine(
                speaker_character_id=str(line["speaker_character_id"]),
                text=str(line["text"]),
                intent=str(line.get("intent") or ""),
            )
            for line in raw_scene.get("dialogue", ())
        )
        scenes.append(
            SceneDraft(
                scene_id=str(raw_scene["scene_id"]),
                title=str(raw_scene["title"]),
                setting=str(raw_scene["setting"]),
                cast_ids=tuple(str(x) for x in raw_scene.get("cast_ids", ())),
                duration_seconds=int(raw_scene["duration_seconds"]),
                objective=str(raw_scene["objective"]),
                action_summary=str(raw_scene["action_summary"]),
                dialogue=dialogue,
            )
        )

    return EpisodeProductionPacket(
        episode_id=request.episode_id,
        season_number=request.season_number,
        episode_number=request.episode_number,
        title=str(payload["title"]),
        logline=str(payload["logline"]),
        topic=request.topic,
        learning_goal=request.learning_goal,
        age_band=request.age_band,
        primary_language=request.primary_language,
        target_duration_seconds=request.target_duration_seconds,
        child_safe_required=request.child_safe_required,
        cast_ids=request.cast_ids,
        continuity_notes=tuple(str(x) for x in payload.get("continuity_notes", ())),
        beats=beats,
        scenes=tuple(scenes),
        owner_approved=False,
    )


class EpisodePlanningStore:
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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    current_version INTEGER NOT NULL,
                    current_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner_decision_at TEXT
                );

                CREATE TABLE IF NOT EXISTS episode_versions (
                    episode_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    packet_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    owner_decision_at TEXT,
                    PRIMARY KEY(episode_id, version)
                );
                """
            )

    def save(
        self,
        packet: EpisodeProductionPacket,
        *,
        created_by: str,
        reason: str,
        status: EpisodeStatus = EpisodeStatus.READY_FOR_OWNER_REVIEW,
    ) -> EpisodeVersion:
        if packet.owner_approved:
            raise InvalidStoryPlanError(
                "planner may not self-approve an episode packet"
            )
        payload = packet.to_payload()
        content_hash = _sha256(payload)
        now = _utc_now()

        with self._connect() as conn:
            current = conn.execute(
                "SELECT current_version, current_hash FROM episodes WHERE episode_id=?",
                (packet.episode_id,),
            ).fetchone()
            version = 1 if current is None else int(current["current_version"]) + 1

            if current is None:
                conn.execute(
                    """
                    INSERT INTO episodes (
                        episode_id, current_version, current_hash,
                        status, created_at, updated_at, owner_decision_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        packet.episode_id,
                        version,
                        content_hash,
                        status.value,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE episodes
                    SET current_version=?, current_hash=?, status=?,
                        updated_at=?, owner_decision_at=NULL
                    WHERE episode_id=?
                    """,
                    (
                        version,
                        content_hash,
                        status.value,
                        now,
                        packet.episode_id,
                    ),
                )

            conn.execute(
                """
                INSERT INTO episode_versions (
                    episode_id, version, content_hash, status, packet_json,
                    created_at, created_by, reason, owner_decision_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    packet.episode_id,
                    version,
                    content_hash,
                    status.value,
                    _stable_json(payload),
                    now,
                    created_by,
                    reason,
                ),
            )

        return self.history(packet.episode_id)[-1]

    def decide(
        self,
        episode_id: str,
        *,
        approved: bool,
    ) -> EpisodeVersion:
        status = EpisodeStatus.APPROVED if approved else EpisodeStatus.REJECTED
        now = _utc_now()

        with self._connect() as conn:
            episode = conn.execute(
                "SELECT current_version FROM episodes WHERE episode_id=?",
                (episode_id,),
            ).fetchone()
            if episode is None:
                raise KeyError(episode_id)

            version = int(episode["current_version"])
            row = conn.execute(
                """
                SELECT packet_json, created_at, created_by, reason
                FROM episode_versions
                WHERE episode_id=? AND version=?
                """,
                (episode_id, version),
            ).fetchone()
            assert row is not None

            payload = json.loads(row["packet_json"])
            payload["owner_approved"] = bool(approved)
            content_hash = _sha256(payload)

            conn.execute(
                """
                UPDATE episodes
                SET current_hash=?, status=?, updated_at=?, owner_decision_at=?
                WHERE episode_id=?
                """,
                (content_hash, status.value, now, now, episode_id),
            )
            conn.execute(
                """
                UPDATE episode_versions
                SET content_hash=?, status=?, packet_json=?, owner_decision_at=?
                WHERE episode_id=? AND version=?
                """,
                (
                    content_hash,
                    status.value,
                    _stable_json(payload),
                    now,
                    episode_id,
                    version,
                ),
            )

        return self.history(episode_id)[-1]

    def history(self, episode_id: str) -> tuple[EpisodeVersion, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM episode_versions
                WHERE episode_id=?
                ORDER BY version
                """,
                (episode_id,),
            ).fetchall()
        return tuple(self._version_from_row(row) for row in rows)

    def get_current(self, episode_id: str) -> EpisodeVersion | None:
        history = self.history(episode_id)
        return history[-1] if history else None

    @staticmethod
    def _version_from_row(row: sqlite3.Row) -> EpisodeVersion:
        packet_payload = json.loads(row["packet_json"])
        request = EpisodeRequest(
            season_number=int(packet_payload["season_number"]),
            episode_number=int(packet_payload["episode_number"]),
            topic=str(packet_payload["topic"]),
            learning_goal=str(packet_payload["learning_goal"]),
            cast_ids=tuple(str(x) for x in packet_payload["cast_ids"]),
            target_duration_seconds=int(packet_payload["target_duration_seconds"]),
            age_band=str(packet_payload["age_band"]),
            primary_language=str(packet_payload["primary_language"]),
            child_safe_required=bool(packet_payload["child_safe_required"]),
        )
        packet = _packet_from_mapping(packet_payload, request)
        if bool(packet_payload.get("owner_approved")):
            packet = EpisodeProductionPacket(
                episode_id=packet.episode_id,
                season_number=packet.season_number,
                episode_number=packet.episode_number,
                title=packet.title,
                logline=packet.logline,
                topic=packet.topic,
                learning_goal=packet.learning_goal,
                age_band=packet.age_band,
                primary_language=packet.primary_language,
                target_duration_seconds=packet.target_duration_seconds,
                child_safe_required=packet.child_safe_required,
                cast_ids=packet.cast_ids,
                continuity_notes=packet.continuity_notes,
                beats=packet.beats,
                scenes=packet.scenes,
                owner_approved=True,
            )

        return EpisodeVersion(
            episode_id=str(row["episode_id"]),
            version=int(row["version"]),
            content_hash=str(row["content_hash"]),
            status=EpisodeStatus(str(row["status"])),
            created_at=str(row["created_at"]),
            created_by=str(row["created_by"]),
            reason=str(row["reason"]),
            owner_decision_at=(
                str(row["owner_decision_at"])
                if row["owner_decision_at"] is not None
                else None
            ),
            packet=packet,
        )


class EpisodePlanningEngine:
    def __init__(
        self,
        *,
        character_store: CharacterBibleStore,
        episode_store: EpisodePlanningStore,
        planner: StoryPlanner,
    ) -> None:
        self.character_store = character_store
        self.episode_store = episode_store
        self.planner = planner

    def build_context(self, request: EpisodeRequest) -> StoryContext:
        known = set(self.character_store.character_ids())
        unknown = [cid for cid in request.cast_ids if cid not in known]
        if unknown:
            raise UnknownStoryCharacterError(
                "unknown character ids: " + ", ".join(sorted(unknown))
            )

        relationships = self.character_store.relationships()
        characters = []
        for character_id in request.cast_ids:
            profile = self.character_store.get_profile(character_id)
            assert profile is not None
            related = {
                rel.to_character_id
                for rel in relationships
                if rel.from_character_id == character_id
            } | {
                rel.from_character_id
                for rel in relationships
                if rel.to_character_id == character_id
            }
            characters.append(
                StoryCharacterContext(
                    character_id=character_id,
                    display_name=profile.display_name,
                    canonical_role=profile.canonical_role,
                    age_stage=profile.age_stage,
                    personality_anchors=profile.personality_anchors,
                    continuity_rules=profile.continuity_rules,
                    related_character_ids=tuple(sorted(related)),
                )
            )

        canon = tuple(
            {
                "fact_id": fact.fact_id,
                "scope_type": fact.scope_type,
                "scope_id": fact.scope_id,
                "fact_key": fact.fact_key,
                "fact_value": fact.fact_value,
                "locked": fact.locked,
            }
            for fact in self.character_store.canon_facts()
        )

        all_events = self.character_store.episode_events()
        recent = tuple(
            {
                "episode_id": event.episode_id,
                "sequence_no": event.sequence_no,
                "event_type": event.event_type,
                "payload": event.payload,
            }
            for event in all_events[-20:]
        )

        return StoryContext(
            episode_id=request.episode_id,
            characters=tuple(characters),
            canon_facts=canon,
            recent_continuity_events=recent,
        )

    def validate_packet(
        self,
        request: EpisodeRequest,
        packet: EpisodeProductionPacket,
    ) -> None:
        errors: list[str] = []
        allowed = set(request.cast_ids)

        if packet.episode_id != request.episode_id:
            errors.append("episode_id mismatch")
        if packet.owner_approved:
            errors.append("planner cannot self-approve")
        if not packet.title.strip():
            errors.append("title is empty")
        if not packet.logline.strip():
            errors.append("logline is empty")
        if len(packet.beats) < 3:
            errors.append("at least 3 story beats are required")
        if len(packet.scenes) < 3:
            errors.append("at least 3 scenes are required")
        if packet.cast_ids != request.cast_ids:
            errors.append("packet cast_ids differ from request")

        total_duration = sum(scene.duration_seconds for scene in packet.scenes)
        if total_duration != request.target_duration_seconds:
            errors.append(
                f"scene durations total {total_duration}, expected "
                f"{request.target_duration_seconds}"
            )

        scene_ids = [scene.scene_id for scene in packet.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            errors.append("duplicate scene_id")

        for scene in packet.scenes:
            if scene.duration_seconds <= 0:
                errors.append(f"{scene.scene_id} duration must be > 0")
            unknown_scene_cast = set(scene.cast_ids) - allowed
            if unknown_scene_cast:
                errors.append(
                    f"{scene.scene_id} has unknown cast: "
                    + ", ".join(sorted(unknown_scene_cast))
                )
            for line in scene.dialogue:
                if line.speaker_character_id not in allowed:
                    errors.append(
                        f"{scene.scene_id} dialogue speaker not allowed: "
                        f"{line.speaker_character_id}"
                    )
                if not line.text.strip():
                    errors.append(f"{scene.scene_id} has empty dialogue")

        if request.child_safe_required and not packet.child_safe_required:
            errors.append("child safety requirement was dropped")

        if errors:
            raise InvalidStoryPlanError("; ".join(errors))

    def plan(
        self,
        request: EpisodeRequest,
        *,
        created_by: str,
        reason: str,
    ) -> EpisodeVersion:
        context = self.build_context(request)
        packet = self.planner.plan(request, context)
        self.validate_packet(request, packet)
        return self.episode_store.save(
            packet,
            created_by=created_by,
            reason=reason,
            status=EpisodeStatus.READY_FOR_OWNER_REVIEW,
        )
