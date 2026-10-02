from ahos.animation_studio import animation_studio_blueprint
from ahos.business_units import BusinessUnitValidationError


def test_animation_studio_has_exactly_20_virtual_workers():
    studio = animation_studio_blueprint()
    assert len(studio.workers) == 20


def test_animation_studio_has_multi_team_hierarchy():
    studio = animation_studio_blueprint()
    assert len(studio.teams) == 8
    assert studio.director_worker_id == "studio-director-01"
    assert studio.owner_controlled is True

    team_ids = {team.team_id for team in studio.teams}
    assert {
        "studio-management",
        "story",
        "art",
        "animation",
        "audio",
        "localization",
        "quality",
        "publishing-growth",
    } == team_ids


def test_every_worker_reaches_studio_director_without_cycle():
    studio = animation_studio_blueprint()
    workers = {worker.worker_id: worker for worker in studio.workers}

    for worker in studio.workers:
        if worker.worker_id == studio.director_worker_id:
            assert worker.reports_to is None
            continue

        seen = set()
        current = worker
        while current.worker_id != studio.director_worker_id:
            assert current.worker_id not in seen
            seen.add(current.worker_id)
            assert current.reports_to is not None
            current = workers[current.reports_to]


def test_paid_ai_and_external_actions_are_disabled_by_default():
    studio = animation_studio_blueprint()
    assert all(worker.paid_ai_enabled is False for worker in studio.workers)
    assert all(worker.external_actions_enabled is False for worker in studio.workers)
    assert all(worker.authority_level == "B" for worker in studio.workers)


def test_studio_contains_required_animation_capabilities():
    studio = animation_studio_blueprint()
    capabilities = set().union(*(worker.capabilities for worker in studio.workers))

    assert {
        "character_bible",
        "episode_memory",
        "screenwriting",
        "storyboard",
        "character_design",
        "comfyui",
        "video_generation",
        "tts",
        "voice_synthesis",
        "localization",
        "qa",
        "child_safety",
        "editing",
        "compositing",
        "analytics",
    }.issubset(capabilities)


def test_owner_keeps_reserved_decision_authority():
    studio = animation_studio_blueprint()
    text = " ".join(studio.owner_reserved_decisions).lower()
    assert "publishing" in text
    assert "payments" in text
    assert "credential" in text
    assert "budget" in text
