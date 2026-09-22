from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .audio_pipeline import DEFAULT_LANGUAGE_POLICIES
from .autonomous_story_room import (
    AutonomousWritersRoom,
    OpenAICompatibleStoryGenerator,
    StoryRoomMemory,
)
from .character_memory import CharacterBibleStore
from .episode_casting import core_cast_voice_briefs
from .scene_graph import ProductionGraphStore, SceneShotPromptAssetGraphBuilder
from .story_engine import EpisodePlanningEngine, EpisodePlanningStore, EpisodeRequest
from .visual_pipeline import RenderManifestStore, VisualProductionPlanner


class AutonomousStudioError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AutonomousStudioResult:
    episode_id: str
    status: str
    approval_packet: Path
    report: Path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)
    return path


def _hash(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _progress(message: str) -> None:
    print(f"[AHOS STUDIO] {message}", file=sys.stderr, flush=True)


def run_autonomous_studio(
    output_directory: str | Path,
    *,
    characters_db: str | Path,
    request: EpisodeRequest,
    generator: OpenAICompatibleStoryGenerator,
) -> AutonomousStudioResult:
    """Run every zero-cost/pre-approval studio department in one transaction.

    The studio intentionally stops before paid/external rendering, TTS, or publishing.
    Those irreversible/cost-bearing actions are represented by one owner gate.
    """
    output = Path(output_directory)
    artifacts = output / "artifacts"
    state = output / "state"
    output.mkdir(parents=True, exist_ok=True)

    characters = CharacterBibleStore(characters_db)
    missing = sorted(set(request.cast_ids) - set(characters.character_ids()))
    if missing:
        raise AutonomousStudioError(
            "character bible is missing requested cast: " + ", ".join(missing)
        )

    _progress("1/7 Story department: AI draft, revisions and deterministic QA")
    room = AutonomousWritersRoom(
        generator=generator,
        memory=StoryRoomMemory(state / "story-room.db"),
    )
    episode_store = EpisodePlanningStore(state / "episodes.db")
    episode = EpisodePlanningEngine(
        character_store=characters,
        episode_store=episode_store,
        planner=room,
    ).plan(
        request,
        created_by="studio-autonomous-departments",
        reason="autonomous multi-department episode preparation",
    )
    episode_payload = episode.packet.to_payload()
    _write_json(artifacts / "episode.json", episode_payload)

    _progress("2/7 Continuity department: locked Character Bible references")
    continuity = {
        "schema": "ahos.continuity-clearance.v1",
        "episode_id": episode.episode_id,
        "cast_ids": list(episode.packet.cast_ids),
        "character_bible_valid": True,
        "relationships": [
            asdict(item)
            for item in characters.relationships()
            if item.from_character_id in request.cast_ids
            or item.to_character_id in request.cast_ids
        ],
    }
    _write_json(artifacts / "continuity-clearance.json", continuity)

    _progress("3/7 Art department: scene, shot, prompt and asset graph")
    graph = SceneShotPromptAssetGraphBuilder(characters).build(episode)
    graph_version = ProductionGraphStore(state / "production-graphs.db").save(
        graph,
        created_by="studio-storyboard-artist-01",
        reason="autonomous owner-review production graph",
    )
    graph_payload = graph.to_payload()
    _write_json(artifacts / "production-graph.json", graph_payload)

    _progress("4/7 Animation department: deterministic render manifest")
    jobs = VisualProductionPlanner().plan(graph_payload)
    render_store = RenderManifestStore(state / "render-jobs.db")
    for job in jobs:
        render_store.upsert_planned(job)
    render_payload = {
        "schema": "ahos.render-job-manifest.v1",
        "episode_id": episode.episode_id,
        "execution_enabled": False,
        "jobs": [job.to_payload() for job in jobs],
    }
    _write_json(artifacts / "render-jobs.json", render_payload)

    _progress("5/7 Voice department: canonical cast and dialogue assignment")
    voice_by_character = {
        item.character_id: item for item in core_cast_voice_briefs()
    }
    missing_voices = sorted(set(request.cast_ids) - set(voice_by_character))
    if missing_voices:
        raise AutonomousStudioError(
            "canonical voice briefs missing: " + ", ".join(missing_voices)
        )
    voice_payload = {
        "schema": "ahos.voice-casting-plan.v1",
        "episode_id": episode.episode_id,
        "execution_enabled": False,
        "characters": [
            asdict(voice_by_character[character_id])
            for character_id in request.cast_ids
        ],
    }
    _write_json(artifacts / "voice-casting.json", voice_payload)

    _progress("6/7 Localization department: seven-language work package")
    units = []
    for scene in episode.packet.scenes:
        for index, line in enumerate(scene.dialogue, start=1):
            for language in DEFAULT_LANGUAGE_POLICIES:
                units.append(
                    {
                        "unit_id": f"{episode.episode_id}:{scene.scene_id}:L{index:03d}:{language.code}",
                        "scene_id": scene.scene_id,
                        "line_id": f"L{index:03d}",
                        "speaker_character_id": line.speaker_character_id,
                        "source_language": request.primary_language,
                        "target_language": language.code,
                        "source_text": line.text,
                        "localized_text": line.text
                        if language.code == request.primary_language
                        else "",
                        "status": "source_ready"
                        if language.code == request.primary_language
                        else "translation_required",
                    }
                )
    localization_payload = {
        "schema": "ahos.localization-work-package.v1",
        "episode_id": episode.episode_id,
        "languages": [item.code for item in DEFAULT_LANGUAGE_POLICIES],
        "units": units,
    }
    _write_json(artifacts / "localization-plan.json", localization_payload)

    _progress("7/7 Studio QA: assembling the single owner decision packet")
    departments = (
        ("story", "completed"),
        ("continuity", "completed"),
        ("art_and_storyboard", "completed"),
        ("animation_planning", "completed"),
        ("voice_casting", "completed"),
        ("localization_planning", "completed"),
        ("quality_and_safety", "completed"),
        ("render_tts_mix", "waiting_owner_approval"),
        ("publishing", "not_requested"),
    )
    evidence = {
        "episode_hash": episode.content_hash,
        "production_graph_hash": graph_version.content_hash,
        "render_job_count": len(jobs),
        "localization_unit_count": len(units),
        "department_statuses": [
            {"department": name, "status": status} for name, status in departments
        ],
    }
    approval = {
        "schema": "ahos.single-owner-decision.v1",
        "episode_id": episode.episode_id,
        "decision_required": "approve_or_reject_external_production_execution",
        "owner_approved": False,
        "paid_execution_enabled": False,
        "external_execution_enabled": False,
        "publishing_enabled": False,
        "evidence": evidence,
        "artifacts": {
            "episode": "artifacts/episode.json",
            "continuity": "artifacts/continuity-clearance.json",
            "production_graph": "artifacts/production-graph.json",
            "render_jobs": "artifacts/render-jobs.json",
            "voice_casting": "artifacts/voice-casting.json",
            "localization": "artifacts/localization-plan.json",
        },
    }
    approval["evidence_hash"] = _hash(approval)
    approval_path = _write_json(output / "OWNER-APPROVAL.json", approval)
    report = {
        "schema": "ahos.autonomous-studio-report.v1",
        "episode_id": episode.episode_id,
        "status": "waiting_owner_approval",
        "owner_action_count": 1,
        "departments": evidence["department_statuses"],
        "approval_packet": str(approval_path),
        "release_ready": False,
    }
    report_path = _write_json(output / "studio-report.json", report)
    _progress("Prepared. One owner approval remains before external production.")
    return AutonomousStudioResult(
        episode.episode_id, "waiting_owner_approval", approval_path, report_path
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the complete pre-approval autonomous animation studio"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--characters-db", required=True)
    parser.add_argument("--season", type=int, default=1)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--learning-goal", required=True)
    parser.add_argument("--cast", default="aden,kaan,esra,harun")
    parser.add_argument("--age-band", default="2-5")
    parser.add_argument("--model", default="openrouter/free")
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--allow-external", action="store_true")
    parser.add_argument("--owner-approved-paid", action="store_true")
    parser.add_argument("--estimated-cost-per-call-usd", type=float, default=0.0)
    parser.add_argument("--daily-budget-usd", type=float, default=0.0)
    parser.add_argument("--provider-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--provider-retry-attempts", type=int, default=3)
    args = parser.parse_args(argv)
    request = EpisodeRequest(
        args.season,
        args.episode,
        args.topic,
        args.learning_goal,
        tuple(item.strip() for item in args.cast.split(",") if item.strip()),
        age_band=args.age_band,
    )
    generator = OpenAICompatibleStoryGenerator(
        model_id=args.model,
        provider_id=args.provider,
        allow_external=args.allow_external,
        owner_approved_paid=args.owner_approved_paid,
        estimated_cost_per_call_usd=args.estimated_cost_per_call_usd,
        daily_budget_usd=args.daily_budget_usd,
        timeout_seconds=args.provider_timeout_seconds,
        retry_attempts=args.provider_retry_attempts,
        progress=_progress,
    )
    result = run_autonomous_studio(
        args.output,
        characters_db=args.characters_db,
        request=request,
        generator=generator,
    )
    print(
        json.dumps(
            {
                "episode_id": result.episode_id,
                "status": result.status,
                "owner_action_count": 1,
                "approval_packet": str(result.approval_packet),
                "report": str(result.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
