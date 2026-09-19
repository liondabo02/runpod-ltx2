from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable

from .character_memory import CharacterBibleStore
from .story_engine import EpisodeProductionPacket, EpisodeVersion


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


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "item"


class ProductionGraphError(RuntimeError):
    pass


class ProductionGraphValidationError(ProductionGraphError):
    pass


class AssetKind(str, Enum):
    CHARACTER_REFERENCE = "character_reference"
    ENVIRONMENT_REFERENCE = "environment_reference"
    SHOT_OUTPUT = "shot_output"


@dataclass(frozen=True, slots=True)
class VisualStyleProfile:
    style_id: str = "family-2d-v1"
    description: str = (
        "2D children's animation, clean readable shapes, warm family-friendly "
        "staging, consistent character identity, simple uncluttered composition"
    )
    negative_prompt: str = (
        "character identity drift, wrong age, wrong family relation, duplicate "
        "character, extra limbs, malformed hands, unreadable face, text artifacts, "
        "watermark, logo, unsafe child content"
    )
    aspect_ratio: str = "16:9"
    frame_rate: int = 24


@dataclass(frozen=True, slots=True)
class AssetNode:
    asset_id: str
    kind: AssetKind
    source_uri: str
    content_hash: str | None
    provenance: tuple[str, ...]
    generated: bool
    required: bool


@dataclass(frozen=True, slots=True)
class PromptPack:
    prompt_id: str
    positive_prompt: str
    negative_prompt: str
    character_ids: tuple[str, ...]
    reference_asset_ids: tuple[str, ...]
    continuity_constraints: tuple[str, ...]
    style_id: str


@dataclass(frozen=True, slots=True)
class ShotNode:
    shot_id: str
    scene_id: str
    ordinal: int
    duration_seconds: int
    camera: str
    framing: str
    action: str
    cast_ids: tuple[str, ...]
    prompt_id: str
    output_asset_id: str


@dataclass(frozen=True, slots=True)
class SceneNode:
    scene_id: str
    title: str
    setting: str
    duration_seconds: int
    environment_asset_id: str
    shot_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EpisodeProductionGraph:
    episode_id: str
    source_episode_version: int
    source_episode_hash: str
    target_duration_seconds: int
    style: VisualStyleProfile
    scenes: tuple[SceneNode, ...]
    shots: tuple[ShotNode, ...]
    prompts: tuple[PromptPack, ...]
    assets: tuple[AssetNode, ...]
    created_at: str

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.production-graph.v1",
            "episode_id": self.episode_id,
            "source_episode_version": self.source_episode_version,
            "source_episode_hash": self.source_episode_hash,
            "target_duration_seconds": self.target_duration_seconds,
            "style": {
                "style_id": self.style.style_id,
                "description": self.style.description,
                "negative_prompt": self.style.negative_prompt,
                "aspect_ratio": self.style.aspect_ratio,
                "frame_rate": self.style.frame_rate,
            },
            "scenes": [
                {
                    "scene_id": scene.scene_id,
                    "title": scene.title,
                    "setting": scene.setting,
                    "duration_seconds": scene.duration_seconds,
                    "environment_asset_id": scene.environment_asset_id,
                    "shot_ids": list(scene.shot_ids),
                }
                for scene in self.scenes
            ],
            "shots": [
                {
                    "shot_id": shot.shot_id,
                    "scene_id": shot.scene_id,
                    "ordinal": shot.ordinal,
                    "duration_seconds": shot.duration_seconds,
                    "camera": shot.camera,
                    "framing": shot.framing,
                    "action": shot.action,
                    "cast_ids": list(shot.cast_ids),
                    "prompt_id": shot.prompt_id,
                    "output_asset_id": shot.output_asset_id,
                }
                for shot in self.shots
            ],
            "prompts": [
                {
                    "prompt_id": prompt.prompt_id,
                    "positive_prompt": prompt.positive_prompt,
                    "negative_prompt": prompt.negative_prompt,
                    "character_ids": list(prompt.character_ids),
                    "reference_asset_ids": list(prompt.reference_asset_ids),
                    "continuity_constraints": list(prompt.continuity_constraints),
                    "style_id": prompt.style_id,
                }
                for prompt in self.prompts
            ],
            "assets": [
                {
                    "asset_id": asset.asset_id,
                    "kind": asset.kind.value,
                    "source_uri": asset.source_uri,
                    "content_hash": asset.content_hash,
                    "provenance": list(asset.provenance),
                    "generated": asset.generated,
                    "required": asset.required,
                }
                for asset in self.assets
            ],
            "created_at": self.created_at,
        }


class SceneShotPromptAssetGraphBuilder:
    """Deterministically converts an episode packet into a production graph.

    This builder is local-only. It does not call AI, ComfyUI, a network,
    rendering service, publishing service, or any paid provider.
    """

    def __init__(
        self,
        character_store: CharacterBibleStore,
        style: VisualStyleProfile | None = None,
    ) -> None:
        self.character_store = character_store
        self.style = style or VisualStyleProfile()

    def build(self, episode: EpisodeVersion) -> EpisodeProductionGraph:
        packet = episode.packet
        known = set(self.character_store.character_ids())
        unknown = set(packet.cast_ids) - known
        if unknown:
            raise ProductionGraphValidationError(
                "episode contains unknown characters: "
                + ", ".join(sorted(unknown))
            )

        assets: dict[str, AssetNode] = {}
        character_asset_ids: dict[str, str] = {}
        character_prompt_fragments: dict[str, str] = {}
        character_constraints: dict[str, tuple[str, ...]] = {}

        for character_id in packet.cast_ids:
            profile = self.character_store.get_profile(character_id)
            history = self.character_store.version_history(character_id)
            assert profile is not None and history
            current = history[-1]

            asset_id = f"charref:{character_id}:v{current.version}"
            character_asset_ids[character_id] = asset_id
            anchors = ", ".join(profile.visual_anchors) or "use approved character reference"
            character_prompt_fragments[character_id] = (
                f"{profile.display_name} ({character_id}), {profile.canonical_role}, "
                f"{profile.age_stage or 'established age'}, visual anchors: {anchors}"
            )
            character_constraints[character_id] = tuple(profile.continuity_rules)

            assets[asset_id] = AssetNode(
                asset_id=asset_id,
                kind=AssetKind.CHARACTER_REFERENCE,
                source_uri=f"character-bible://{character_id}/v{current.version}",
                content_hash=current.content_hash,
                provenance=(
                    f"character:{character_id}",
                    f"character-version:{current.version}",
                ),
                generated=False,
                required=True,
            )

        scenes: list[SceneNode] = []
        shots: list[ShotNode] = []
        prompts: list[PromptPack] = []

        for scene_index, scene in enumerate(packet.scenes, start=1):
            unknown_scene = set(scene.cast_ids) - known
            if unknown_scene:
                raise ProductionGraphValidationError(
                    f"{scene.scene_id} contains unknown cast: "
                    + ", ".join(sorted(unknown_scene))
                )

            env_key = _slug(scene.setting)
            env_asset_id = f"envref:{env_key}"
            if env_asset_id not in assets:
                assets[env_asset_id] = AssetNode(
                    asset_id=env_asset_id,
                    kind=AssetKind.ENVIRONMENT_REFERENCE,
                    source_uri=f"environment-memory://{env_key}",
                    content_hash=None,
                    provenance=(
                        f"scene-setting:{scene.setting}",
                        "environment-source:story-packet",
                    ),
                    generated=False,
                    required=True,
                )

            first = scene.duration_seconds // 2
            second = scene.duration_seconds - first
            shot_specs = (
                (
                    1,
                    first,
                    "static establishing camera",
                    "wide shot",
                    f"Establish {scene.setting}; {scene.action_summary}",
                ),
                (
                    2,
                    second,
                    "gentle eye-level camera",
                    "medium interaction shot",
                    (
                        f"Continue the scene objective: {scene.objective}. "
                        f"Show character interaction and continuity."
                    ),
                ),
            )

            scene_shot_ids: list[str] = []
            for ordinal, duration, camera, framing, action in shot_specs:
                shot_id = f"{scene.scene_id}-SHOT-{ordinal:02d}"
                prompt_id = f"prompt:{packet.episode_id}:{shot_id}"
                output_asset_id = f"render:{packet.episode_id}:{shot_id}"

                ref_ids = (
                    env_asset_id,
                    *(
                        character_asset_ids[character_id]
                        for character_id in scene.cast_ids
                    ),
                )
                constraints = tuple(
                    dict.fromkeys(
                        rule
                        for character_id in scene.cast_ids
                        for rule in character_constraints[character_id]
                    )
                )

                positive = "; ".join(
                    (
                        self.style.description,
                        f"episode {packet.episode_id}",
                        f"scene: {scene.title}",
                        f"setting: {scene.setting}",
                        f"camera: {camera}",
                        f"framing: {framing}",
                        f"action: {action}",
                        "characters: "
                        + " | ".join(
                            character_prompt_fragments[character_id]
                            for character_id in scene.cast_ids
                        ),
                        "preserve exact approved character identity and family relationships",
                    )
                )

                prompts.append(
                    PromptPack(
                        prompt_id=prompt_id,
                        positive_prompt=positive,
                        negative_prompt=self.style.negative_prompt,
                        character_ids=scene.cast_ids,
                        reference_asset_ids=tuple(ref_ids),
                        continuity_constraints=constraints,
                        style_id=self.style.style_id,
                    )
                )
                shots.append(
                    ShotNode(
                        shot_id=shot_id,
                        scene_id=scene.scene_id,
                        ordinal=ordinal,
                        duration_seconds=duration,
                        camera=camera,
                        framing=framing,
                        action=action,
                        cast_ids=scene.cast_ids,
                        prompt_id=prompt_id,
                        output_asset_id=output_asset_id,
                    )
                )
                assets[output_asset_id] = AssetNode(
                    asset_id=output_asset_id,
                    kind=AssetKind.SHOT_OUTPUT,
                    source_uri=f"pending-render://{packet.episode_id}/{shot_id}",
                    content_hash=None,
                    provenance=(
                        f"episode:{packet.episode_id}",
                        f"source-episode-hash:{episode.content_hash}",
                        f"scene:{scene.scene_id}",
                        f"prompt:{prompt_id}",
                    ),
                    generated=False,
                    required=True,
                )
                scene_shot_ids.append(shot_id)

            scenes.append(
                SceneNode(
                    scene_id=scene.scene_id,
                    title=scene.title,
                    setting=scene.setting,
                    duration_seconds=scene.duration_seconds,
                    environment_asset_id=env_asset_id,
                    shot_ids=tuple(scene_shot_ids),
                )
            )

        graph = EpisodeProductionGraph(
            episode_id=packet.episode_id,
            source_episode_version=episode.version,
            source_episode_hash=episode.content_hash,
            target_duration_seconds=packet.target_duration_seconds,
            style=self.style,
            scenes=tuple(scenes),
            shots=tuple(shots),
            prompts=tuple(prompts),
            assets=tuple(sorted(assets.values(), key=lambda x: x.asset_id)),
            created_at=_utc_now(),
        )
        self.validate(graph)
        return graph

    def validate(self, graph: EpisodeProductionGraph) -> None:
        errors: list[str] = []
        scene_by_id = {scene.scene_id: scene for scene in graph.scenes}
        shot_by_id = {shot.shot_id: shot for shot in graph.shots}
        prompt_by_id = {prompt.prompt_id: prompt for prompt in graph.prompts}
        asset_by_id = {asset.asset_id: asset for asset in graph.assets}

        if len(scene_by_id) != len(graph.scenes):
            errors.append("duplicate scene ids")
        if len(shot_by_id) != len(graph.shots):
            errors.append("duplicate shot ids")
        if len(prompt_by_id) != len(graph.prompts):
            errors.append("duplicate prompt ids")
        if len(asset_by_id) != len(graph.assets):
            errors.append("duplicate asset ids")

        total_duration = sum(scene.duration_seconds for scene in graph.scenes)
        if total_duration != graph.target_duration_seconds:
            errors.append(
                f"scene duration total {total_duration} != "
                f"{graph.target_duration_seconds}"
            )

        for scene in graph.scenes:
            local_shots = [shot_by_id.get(shot_id) for shot_id in scene.shot_ids]
            if any(shot is None for shot in local_shots):
                errors.append(f"{scene.scene_id} references missing shot")
                continue
            local_duration = sum(shot.duration_seconds for shot in local_shots if shot)
            if local_duration != scene.duration_seconds:
                errors.append(
                    f"{scene.scene_id} shot durations {local_duration} != "
                    f"{scene.duration_seconds}"
                )
            if scene.environment_asset_id not in asset_by_id:
                errors.append(f"{scene.scene_id} missing environment asset")

        for shot in graph.shots:
            if shot.scene_id not in scene_by_id:
                errors.append(f"{shot.shot_id} references unknown scene")
            if shot.prompt_id not in prompt_by_id:
                errors.append(f"{shot.shot_id} missing prompt")
            if shot.output_asset_id not in asset_by_id:
                errors.append(f"{shot.shot_id} missing output asset")
            if shot.duration_seconds <= 0:
                errors.append(f"{shot.shot_id} has invalid duration")

        for prompt in graph.prompts:
            if not prompt.positive_prompt.strip():
                errors.append(f"{prompt.prompt_id} empty positive prompt")
            if not prompt.negative_prompt.strip():
                errors.append(f"{prompt.prompt_id} empty negative prompt")
            for asset_id in prompt.reference_asset_ids:
                if asset_id not in asset_by_id:
                    errors.append(
                        f"{prompt.prompt_id} references unknown asset {asset_id}"
                    )

        if any(asset.generated for asset in graph.assets):
            errors.append("STUDIO-004 graph must not claim rendered assets")

        if errors:
            raise ProductionGraphValidationError("; ".join(errors))


@dataclass(frozen=True, slots=True)
class GraphVersion:
    episode_id: str
    version: int
    content_hash: str
    created_at: str
    created_by: str
    reason: str
    graph: EpisodeProductionGraph


class ProductionGraphStore:
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
                CREATE TABLE IF NOT EXISTS production_graphs (
                    episode_id TEXT PRIMARY KEY,
                    current_version INTEGER NOT NULL,
                    current_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS production_graph_versions (
                    episode_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    PRIMARY KEY(episode_id, version)
                );
                """
            )

    def save(
        self,
        graph: EpisodeProductionGraph,
        *,
        created_by: str,
        reason: str,
    ) -> GraphVersion:
        payload = graph.to_payload()
        # created_at is metadata, not semantic content.
        semantic = dict(payload)
        semantic.pop("created_at", None)
        content_hash = _sha256(semantic)
        now = _utc_now()

        with self._connect() as conn:
            current = conn.execute(
                "SELECT current_version FROM production_graphs WHERE episode_id=?",
                (graph.episode_id,),
            ).fetchone()
            version = 1 if current is None else int(current["current_version"]) + 1

            if current is None:
                conn.execute(
                    """
                    INSERT INTO production_graphs (
                        episode_id, current_version, current_hash, updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (graph.episode_id, version, content_hash, now),
                )
            else:
                conn.execute(
                    """
                    UPDATE production_graphs
                    SET current_version=?, current_hash=?, updated_at=?
                    WHERE episode_id=?
                    """,
                    (version, content_hash, now, graph.episode_id),
                )

            conn.execute(
                """
                INSERT INTO production_graph_versions (
                    episode_id, version, content_hash, payload_json,
                    created_at, created_by, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    graph.episode_id,
                    version,
                    content_hash,
                    _stable_json(payload),
                    now,
                    created_by,
                    reason,
                ),
            )

        return GraphVersion(
            episode_id=graph.episode_id,
            version=version,
            content_hash=content_hash,
            created_at=now,
            created_by=created_by,
            reason=reason,
            graph=graph,
        )

    def current_payload(self, episode_id: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT v.payload_json
                FROM production_graphs g
                JOIN production_graph_versions v
                  ON v.episode_id=g.episode_id
                 AND v.version=g.current_version
                WHERE g.episode_id=?
                """,
                (episode_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def history_count(self, episode_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM production_graph_versions
                WHERE episode_id=?
                """,
                (episode_id,),
            ).fetchone()
        return int(row["count"])


def export_graph(graph: EpisodeProductionGraph, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(graph.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination
