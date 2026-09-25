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

    def localization_generator(prompt_text):
        prompt = json.loads(prompt_text)
        return json.dumps(
            {
                "translations": [
                    {
                        "unit_id": unit["unit_id"],
                        "localized_text": (
                            unit["source_text"]
                            if unit["target_language"] == unit["source_language"]
                            else f"{unit['target_language']} çeviri: {unit['source_text']}"
                        ),
                    }
                    for unit in prompt["units"]
                ]
            },
            ensure_ascii=False,
        )

    result = run_autonomous_studio(
        tmp_path / "studio",
        characters_db=character_db,
        request=request,
        generator=lambda _: json.dumps(story, ensure_ascii=False),
        localization_generator=localization_generator,
    )

    assert result.status == "waiting_owner_approval"
    approval = json.loads(result.approval_packet.read_text(encoding="utf-8"))
    assert approval["owner_approved"] is False
    assert approval["paid_execution_enabled"] is False
    assert approval["external_execution_enabled"] is False
    assert approval["evidence"]["render_job_count"] == 10
    assert approval["evidence"]["localization_unit_count"] > 0
    localization = json.loads(
        (tmp_path / "studio" / "artifacts" / "localization-plan.json").read_text(
            encoding="utf-8"
        )
    )
    assert localization["status"] == "machine_qa_approved"
    assert all(unit["localized_text"] for unit in localization["units"])
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
