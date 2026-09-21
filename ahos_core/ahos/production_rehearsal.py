from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .audio_pipeline import DEFAULT_LANGUAGE_POLICIES
from .character_memory import CharacterBibleStore, CharacterProfile, CharacterRelationship
from .scene_graph import ProductionGraphStore, SceneShotPromptAssetGraphBuilder
from .story_engine import (
    DeterministicLocalStoryPlanner,
    EpisodePlanningEngine,
    EpisodePlanningStore,
    EpisodeRequest,
)
from .visual_pipeline import RenderManifestStore, VisualProductionPlanner


class ProductionRehearsalError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RehearsalResult:
    episode_id: str
    status: str
    output_directory: Path
    report_path: Path
    render_job_count: int
    dialogue_line_count: int
    localization_unit_count: int


_LOCKED_FIELDS = frozenset(
    {
        "display_name",
        "canonical_role",
        "family_group",
        "age_stage",
        "visual_anchors",
        "personality_anchors",
        "voice_anchors",
        "continuity_rules",
    }
)


def _profile(
    character_id: str,
    name: str,
    role: str,
    age: str,
    visual: Sequence[str],
    personality: Sequence[str],
    voice: Sequence[str],
    rules: Sequence[str],
) -> CharacterProfile:
    return CharacterProfile(
        character_id=character_id,
        display_name=name,
        canonical_role=role,
        family_group="aden-family-world",
        age_stage=age,
        visual_anchors=tuple(visual),
        personality_anchors=tuple(personality),
        voice_anchors=tuple(voice),
        continuity_rules=tuple(rules),
        locked_fields=_LOCKED_FIELDS,
    )


CANONICAL_CAST = (
    _profile("aden", "Aden", "lead child", "3-year-old child", ("small child proportions", "expressive brown eyes"), ("curious", "kind", "brave"), ("preschool child", "warm", "clear"), ("Aden remains Kaan's older brother.",)),
    _profile("kaan", "Kaan", "lead infant sibling", "1-year-old toddler", ("toddler proportions", "round cheeks"), ("playful", "observant"), ("toddler vocalizations", "no adult sentence voice"), ("Kaan remains Aden's younger brother.",)),
    _profile("esra", "Esra", "mother", "adult", ("modest clothing", "headscarf"), ("patient", "protective"), ("warm adult female",), ("Esra is Aden and Kaan's mother.",)),
    _profile("ahmet", "Ahmet", "father", "adult", ("family-canon appearance",), ("supportive", "calm"), ("calm adult male",), ("Ahmet may be absent from some episodes.",)),
    _profile("esma", "Esma", "maternal aunt", "adult", ("headscarf", "pregnancy continuity"), ("caring", "thoughtful"), ("warm adult female",), ("Esma remains Harun's spouse and the children's aunt.",)),
    _profile("harun", "Harun", "uncle and family problem-solver", "adult", ("tall", "long hair", "confident silhouette"), ("decisive", "protective", "resourceful"), ("confident adult male",), ("Harun remains the prominent organizing uncle.",)),
    _profile("veysel", "Veysel", "family adult", "adult", ("family-canon appearance",), ("friendly",), ("adult male",), ("Veysel remains Öznur's spouse.",)),
    _profile("oznur", "Öznur", "family adult", "adult", ("headscarf",), ("gentle",), ("adult female",), ("Öznur remains Salih and Medine's mother.",)),
    _profile("salih", "Salih", "young child", "2-year-old child", ("toddler proportions",), ("energetic",), ("young child",), ("Salih remains Veysel and Öznur's child.",)),
    _profile("medine", "Medine", "infant", "2-month-old infant", ("infant proportions",), ("calm",), ("infant vocalizations only",), ("Medine never speaks adult-like sentences.",)),
    _profile("davut", "Davut", "family adult", "adult", ("large build", "long hair"), ("humorous",), ("adult male",), ("Davut remains Fatoş's spouse.",)),
    _profile("fatos", "Fatoş", "family adult", "adult", ("family-canon appearance",), ("practical",), ("adult female",), ("Fatoş remains mother of Emoş, Berzan, Aras and Ramin.",)),
    _profile("emos", "Emoş", "young child", "4-year-old child", ("preschool proportions",), ("imaginative",), ("preschool child",), ("Emoş remains the older sibling of the twins and Ramin.",)),
    _profile("berzan", "Berzan", "twin child", "2-year-old child", ("toddler proportions", "distinct Berzan identity"), ("adventurous",), ("young child",), ("Berzan remains Aras's twin; identities must never swap.",)),
    _profile("aras", "Aras", "twin child", "2-year-old child", ("toddler proportions", "distinct Aras identity"), ("careful",), ("young child",), ("Aras remains Berzan's twin; identities must never swap.",)),
    _profile("ramin", "Ramin", "infant", "1-month-old infant", ("newborn proportions",), ("calm",), ("infant vocalizations only",), ("Ramin never speaks adult-like sentences.",)),
)


RELATIONSHIPS = (
    CharacterRelationship("aden-sibling-kaan", "aden", "kaan", "sibling_of", "Older brother and younger brother."),
    CharacterRelationship("esra-mother-aden", "esra", "aden", "mother_of"),
    CharacterRelationship("esra-mother-kaan", "esra", "kaan", "mother_of"),
    CharacterRelationship("ahmet-father-aden", "ahmet", "aden", "father_of"),
    CharacterRelationship("ahmet-father-kaan", "ahmet", "kaan", "father_of"),
    CharacterRelationship("esma-spouse-harun", "esma", "harun", "spouse_of"),
    CharacterRelationship("berzan-twin-aras", "berzan", "aras", "twin_of"),
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def _sha256_payload(payload: object) -> str:
    material = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def run_rehearsal(
    output_directory: str | Path,
    *,
    season_number: int = 1,
    episode_number: int = 1,
    topic: str = "Kayıp Renkler Haritası",
    learning_goal: str = "paylaşmayı, birlikte düşünmeyi ve yardımlaşmayı öğrenmek",
    owner_approve_story: bool = False,
) -> RehearsalResult:
    output = Path(output_directory)
    report_path = output / "rehearsal-report.json"
    if report_path.exists():
        raise ProductionRehearsalError(
            f"rehearsal output already exists: {report_path}; use a new directory"
        )
    output.mkdir(parents=True, exist_ok=True)
    state = output / "state"
    artifacts = output / "artifacts"

    characters = CharacterBibleStore(state / "characters.db")
    for profile in CANONICAL_CAST:
        characters.upsert_profile(
            profile,
            author="studio-continuity-editor-01",
            reason="seed locked professional canonical cast",
        )
    for relationship in RELATIONSHIPS:
        characters.add_relationship(relationship)

    request = EpisodeRequest(
        season_number=season_number,
        episode_number=episode_number,
        topic=topic,
        learning_goal=learning_goal,
        cast_ids=("aden", "kaan", "esra", "harun"),
        target_duration_seconds=480,
        primary_language="tr",
    )
    episode_store = EpisodePlanningStore(state / "episodes.db")
    engine = EpisodePlanningEngine(
        character_store=characters,
        episode_store=episode_store,
        planner=DeterministicLocalStoryPlanner(),
    )
    episode = engine.plan(
        request,
        created_by="studio-story-director-01",
        reason="deterministic professional episode production rehearsal",
    )
    if owner_approve_story:
        episode = episode_store.decide(episode.episode_id, approved=True)

    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)
    graph_version = ProductionGraphStore(state / "production-graphs.db").save(
        graph,
        created_by="studio-animation-director-01",
        reason="traceable rehearsal production graph",
    )
    render_jobs = VisualProductionPlanner().plan(graph.to_payload())
    render_store = RenderManifestStore(state / "render-jobs.db")
    for job in render_jobs:
        render_store.upsert_planned(job)

    dialogue = [
        (scene.scene_id, line_index, line)
        for scene in episode.packet.scenes
        for line_index, line in enumerate(scene.dialogue, start=1)
    ]
    localization_units = []
    for scene_id, line_index, line in dialogue:
        for policy in DEFAULT_LANGUAGE_POLICIES:
            localization_units.append(
                {
                    "unit_id": f"{episode.episode_id}:{scene_id}:L{line_index:03d}:{policy.code}",
                    "scene_id": scene_id,
                    "speaker_character_id": line.speaker_character_id,
                    "source_language": "tr",
                    "target_language": policy.code,
                    "source_text": line.text,
                    "localized_text": line.text if policy.code == "tr" else "",
                    "status": "source_ready" if policy.code == "tr" else "translation_required",
                    "human_review_required": policy.human_review_required,
                }
            )

    episode_payload = episode.packet.to_payload()
    graph_payload = graph.to_payload()
    render_payload = {
        "schema": "ahos.render-job-manifest.v1",
        "episode_id": episode.episode_id,
        "execution_enabled": False,
        "owner_approval_required": True,
        "jobs": [job.to_payload() for job in render_jobs],
    }
    localization_payload = {
        "schema": "ahos.localization-plan.v1",
        "episode_id": episode.episode_id,
        "languages": [policy.code for policy in DEFAULT_LANGUAGE_POLICIES],
        "units": localization_units,
    }
    _write_json(artifacts / "episode.json", episode_payload)
    _write_json(artifacts / "production-graph.json", graph_payload)
    _write_json(artifacts / "render-jobs.json", render_payload)
    _write_json(artifacts / "localization-plan.json", localization_payload)

    story_approved = episode.packet.owner_approved
    status = "blocked_pending_external_assets" if story_approved else "awaiting_owner_story_approval"
    checks = (
        {"check_id": "canonical-cast", "passed": len(characters.character_ids()) == 16, "detail": "16 locked recurring character profiles are present."},
        {"check_id": "episode-duration", "passed": sum(scene.duration_seconds for scene in episode.packet.scenes) == 480, "detail": "Episode timeline is exactly 480 seconds."},
        {"check_id": "traceable-render-plan", "passed": len(render_jobs) == len(graph.shots), "detail": "Every shot has one deterministic render job."},
        {"check_id": "seven-language-plan", "passed": len({unit["target_language"] for unit in localization_units}) == 7, "detail": "TR, Kurmanji, DE, AR, FR, ES and EN are planned."},
        {"check_id": "story-owner-approval", "passed": story_approved, "detail": "Story approval is explicit and never inferred."},
        {"check_id": "external-execution-disabled", "passed": True, "detail": "No paid render, TTS, network or publishing call was made."},
    )
    report = {
        "schema": "ahos.production-rehearsal-report.v1",
        "episode_id": episode.episode_id,
        "status": status,
        "release_ready": False,
        "story_version": episode.version,
        "story_hash": episode.content_hash,
        "production_graph_version": graph_version.version,
        "production_graph_hash": graph_version.content_hash,
        "counts": {
            "canonical_characters": len(characters.character_ids()),
            "scenes": len(graph.scenes),
            "shots": len(graph.shots),
            "render_jobs": len(render_jobs),
            "dialogue_lines": len(dialogue),
            "localization_units": len(localization_units),
            "languages": len(DEFAULT_LANGUAGE_POLICIES),
        },
        "checks": list(checks),
        "blockers": (
            ["owner_story_approval"] if not story_approved else []
        ) + [
            "approved_character_reference_images",
            "approved_canonical_voice_enrollments",
            "human_reviewed_localizations",
            "owner_approved_paid_render_and_tts_execution",
            "rendered_media_and_final_quality_evidence",
        ],
        "artifacts": {
            "episode": "artifacts/episode.json",
            "production_graph": "artifacts/production-graph.json",
            "render_jobs": "artifacts/render-jobs.json",
            "localization_plan": "artifacts/localization-plan.json",
        },
    }
    report["evidence_hash"] = _sha256_payload(report)
    _write_json(report_path, report)
    return RehearsalResult(
        episode_id=episode.episode_id,
        status=status,
        output_directory=output,
        report_path=report_path,
        render_job_count=len(render_jobs),
        dialogue_line_count=len(dialogue),
        localization_unit_count=len(localization_units),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a local, fail-closed AHOS professional episode production rehearsal"
    )
    parser.add_argument("--output", required=True, help="New output directory")
    parser.add_argument("--season", type=int, default=1)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--topic", default="Kayıp Renkler Haritası")
    parser.add_argument(
        "--learning-goal",
        default="paylaşmayı, birlikte düşünmeyi ve yardımlaşmayı öğrenmek",
    )
    parser.add_argument(
        "--owner-approve-story",
        action="store_true",
        help="Record explicit owner approval for this local story packet only",
    )
    args = parser.parse_args(argv)
    try:
        result = run_rehearsal(
            args.output,
            season_number=args.season,
            episode_number=args.episode,
            topic=args.topic,
            learning_goal=args.learning_goal,
            owner_approve_story=args.owner_approve_story,
        )
    except (OSError, ValueError, ProductionRehearsalError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "episode_id": result.episode_id,
                "status": result.status,
                "report": str(result.report_path),
                "render_jobs": result.render_job_count,
                "dialogue_lines": result.dialogue_line_count,
                "localization_units": result.localization_unit_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
