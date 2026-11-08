import pytest

from ahos.episode_assembly import (
    AssemblyValidationError,
    EpisodeAssemblyPlanner,
    ReleaseAsset,
)


def graph():
    return {
        "episode_id": "S01E001",
        "target_duration_seconds": 8,
        "shots": [
            {"shot_id": "s1", "output_asset_id": "video:s1"},
            {"shot_id": "s2", "output_asset_id": "video:s2"},
        ],
    }


def complete_assets():
    return (
        ReleaseAsset("video:s1", "shot_video", "s1.mp4", 4, content_hash="a" * 64),
        ReleaseAsset("video:s2", "shot_video", "s2.mp4", 4, content_hash="b" * 64),
        ReleaseAsset("mix:tr", "final_mix", "tr.wav", 8, "tr", "c" * 64),
        ReleaseAsset("sub:tr", "subtitle", "tr.srt", 8, "tr", "d" * 64),
    )


def test_complete_package_passes_all_gates():
    package = EpisodeAssemblyPlanner().build(
        graph=graph(), assets=complete_assets(),
        child_safe_approved=True, continuity_approved=True,
    )
    assert package.release_ready is True
    assert len(package.package_hash) == 64
    assert {q.category for q in package.qa_results} == EpisodeAssemblyPlanner.REQUIRED_QA_CATEGORIES


def test_assembly_order_is_graph_order_then_audio_and_subtitles():
    package = EpisodeAssemblyPlanner().build(
        graph=graph(), assets=complete_assets(),
        child_safe_approved=True, continuity_approved=True,
    )
    assert [s["asset_id"] for s in package.assembly_steps[:2]] == ["video:s1", "video:s2"]
    assert package.assembly_steps[2]["operation"] == "mux_audio"
    assert package.assembly_steps[3]["operation"] == "attach_subtitle"


@pytest.mark.parametrize("safety,continuity", [(False, True), (True, False)])
def test_human_safety_and_continuity_gates_fail_closed(safety, continuity):
    package = EpisodeAssemblyPlanner().build(
        graph=graph(), assets=complete_assets(),
        child_safe_approved=safety, continuity_approved=continuity,
    )
    assert package.release_ready is False


def test_missing_shot_audio_or_subtitle_fails_release():
    assets = (complete_assets()[0],)
    package = EpisodeAssemblyPlanner().build(
        graph=graph(), assets=assets,
        child_safe_approved=True, continuity_approved=True,
    )
    assert package.release_ready is False
    assert sum(not q.passed for q in package.qa_results) >= 3


def test_duration_mismatch_fails_technical_gate():
    assets = list(complete_assets())
    assets[1] = ReleaseAsset("video:s2", "shot_video", "s2.mp4", 3, content_hash="b" * 64)
    package = EpisodeAssemblyPlanner().build(
        graph=graph(), assets=assets,
        child_safe_approved=True, continuity_approved=True,
    )
    assert package.release_ready is False
    assert next(q for q in package.qa_results if q.check_id == "picture-duration").passed is False


def test_duplicate_assets_and_empty_timeline_are_rejected():
    planner = EpisodeAssemblyPlanner()
    duplicate = complete_assets() + (complete_assets()[0],)
    with pytest.raises(AssemblyValidationError):
        planner.build(graph=graph(), assets=duplicate, child_safe_approved=True, continuity_approved=True)
    with pytest.raises(AssemblyValidationError):
        planner.build(graph={"episode_id": "x", "shots": []}, assets=(), child_safe_approved=True, continuity_approved=True)
