import json

from ahos.autonomous_studio import run_autonomous_studio
from ahos.character_memory import CharacterBibleStore
from ahos.production_rehearsal import (
    CANONICAL_CAST,
    RELATIONSHIPS,
    ProfessionalPilotStoryPlanner,
)
from ahos.story_engine import EpisodePlanningEngine, EpisodePlanningStore, EpisodeRequest


def test_autonomous_studio_prepares_every_department_for_one_owner_gate(tmp_path):
    character_db = tmp_path / "characters.db"
    characters = CharacterBibleStore(character_db)
    for profile in CANONICAL_CAST:
        characters.upsert_profile(profile, author="test", reason="canonical test seed")
    for relationship in RELATIONSHIPS:
        characters.add_relationship(relationship)

    request = EpisodeRequest(
        1,
        1,
        "Kayıp Renkler Haritası",
        "paylaşma ve yardımlaşma",
        ("aden", "kaan", "esra", "harun"),
        age_band="2-5",
    )
    context = EpisodePlanningEngine(
        character_store=characters,
        episode_store=EpisodePlanningStore(tmp_path / "context-episodes.db"),
        planner=ProfessionalPilotStoryPlanner(),
    ).build_context(request)
    story = ProfessionalPilotStoryPlanner().plan(request, context).to_payload()

    result = run_autonomous_studio(
        tmp_path / "studio",
        characters_db=character_db,
        request=request,
        generator=lambda _: json.dumps(story, ensure_ascii=False),
    )

    assert result.status == "waiting_owner_approval"
    approval = json.loads(result.approval_packet.read_text(encoding="utf-8"))
    assert approval["owner_approved"] is False
    assert approval["paid_execution_enabled"] is False
    assert approval["external_execution_enabled"] is False
    assert approval["evidence"]["render_job_count"] == 10
    assert approval["evidence"]["localization_unit_count"] > 0
    completed = {
        item["department"]
        for item in approval["evidence"]["department_statuses"]
        if item["status"] == "completed"
    }
    assert completed == {
        "story",
        "continuity",
        "art_and_storyboard",
        "animation_planning",
        "voice_casting",
        "localization_planning",
        "quality_and_safety",
    }
    for relative in approval["artifacts"].values():
        assert (tmp_path / "studio" / relative).is_file()
