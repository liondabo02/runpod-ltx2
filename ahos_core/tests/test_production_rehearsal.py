import json

import pytest

from ahos.production_rehearsal import ProductionRehearsalError, run_rehearsal


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_rehearsal_builds_traceable_professional_episode_without_execution(tmp_path):
    result = run_rehearsal(tmp_path / "episode")

    assert result.episode_id == "S01E001"
    assert result.status == "awaiting_owner_story_approval"
    assert result.render_job_count == 10
    assert result.dialogue_line_count == 10
    assert result.localization_unit_count == 70

    report = load(result.report_path)
    episode = load(result.output_directory / "artifacts" / "episode.json")
    graph = load(result.output_directory / "artifacts" / "production-graph.json")
    renders = load(result.output_directory / "artifacts" / "render-jobs.json")
    localization = load(result.output_directory / "artifacts" / "localization-plan.json")

    assert report["release_ready"] is False
    assert "owner_story_approval" in report["blockers"]
    assert len(report["evidence_hash"]) == 64
    assert episode["owner_approved"] is False
    assert sum(scene["duration_seconds"] for scene in episode["scenes"]) == 480
    assert {shot["output_asset_id"] for shot in graph["shots"]} == {
        job["output_asset_id"] for job in renders["jobs"]
    }
    assert renders["execution_enabled"] is False
    assert {unit["target_language"] for unit in localization["units"]} == {
        "tr", "ku-latn", "de", "ar", "fr", "es", "en"
    }
    assert all(
        unit["status"] == "translation_required"
        for unit in localization["units"]
        if unit["target_language"] != "tr"
    )


def test_explicit_story_approval_advances_only_to_external_asset_gate(tmp_path):
    result = run_rehearsal(tmp_path / "approved", owner_approve_story=True)
    report = load(result.report_path)
    episode = load(result.output_directory / "artifacts" / "episode.json")

    assert result.status == "blocked_pending_external_assets"
    assert episode["owner_approved"] is True
    assert "owner_story_approval" not in report["blockers"]
    assert report["release_ready"] is False
    assert "owner_approved_paid_render_and_tts_execution" in report["blockers"]


def test_rehearsal_refuses_to_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "episode"
    run_rehearsal(output)

    with pytest.raises(ProductionRehearsalError, match="already exists"):
        run_rehearsal(output)
