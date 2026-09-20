import pytest

from ahos.music_sfx_supervision import (
    MusicSfxSupervisionError,
    MusicSfxSupervisor,
    SoundAssetEvidence,
    SoundCue,
)


SHA = "a" * 64


def asset(asset_id, kind, **overrides):
    values = dict(
        asset_id=asset_id, kind=kind, uri=f"private://{asset_id}.wav", sha256=SHA,
        source_uri="private://rights/evidence.json", license_id="CC-BY-4.0",
        rights_holder="AHOS Studio", commercial_rights_confirmed=True,
        attribution_text="Example Artist — CC BY 4.0",
    )
    values.update(overrides)
    return SoundAssetEvidence(**values)


def cue(cue_id, asset_id, kind, start, end, **overrides):
    values = dict(
        cue_id=cue_id, scene_id="scene-1", asset_id=asset_id, kind=kind,
        start_seconds=start, end_seconds=end, purpose="Support the emotional beat",
        dialogue_ducking_db=-8, child_safe_reviewed=True, creative_reviewed=True,
    )
    values.update(overrides)
    return SoundCue(**values)


def complete_package():
    return MusicSfxSupervisor().build(
        episode_id="S01E001", episode_duration_seconds=60,
        assets=(asset("music-1", "music"), asset("sfx-1", "sfx")),
        cues=(cue("m1", "music-1", "music", 0, 60), cue("fx1", "sfx-1", "sfx", 4, 5)),
    )


def test_complete_package_is_ready_and_deterministic():
    first = complete_package()
    second = complete_package()
    assert first.ready is True
    assert first.package_hash == second.package_hash
    assert all(first.qa.values())


@pytest.mark.parametrize("field", ["commercial_rights_confirmed", "child_safe_reviewed", "creative_reviewed"])
def test_human_and_rights_gates_fail_closed(field):
    sound_asset = asset("music-1", "music", commercial_rights_confirmed=False) if field == "commercial_rights_confirmed" else asset("music-1", "music")
    sound_cue = cue("m1", "music-1", "music", 0, 60, **({field: False} if field != "commercial_rights_confirmed" else {}))
    package = MusicSfxSupervisor().build(
        episode_id="E1", episode_duration_seconds=60,
        assets=(sound_asset, asset("sfx-1", "sfx")),
        cues=(sound_cue, cue("fx1", "sfx-1", "sfx", 4, 5)),
    )
    assert package.ready is False


def test_bad_timeline_missing_reference_and_overlap_fail_qa():
    package = MusicSfxSupervisor().build(
        episode_id="E1", episode_duration_seconds=10,
        assets=(asset("music-1", "music"),),
        cues=(cue("m1", "music-1", "music", 0, 7), cue("m2", "missing", "music", 6, 12)),
    )
    assert package.ready is False
    assert package.qa["timeline_valid"] is False
    assert package.qa["asset_references_valid"] is False
    assert package.qa["music_non_overlapping"] is False


@pytest.mark.parametrize("bad_asset", [
    asset("x", "unknown"),
    asset("x", "music", sha256="bad"),
    asset("x", "music", generated_with_ai=True, generator_id=None),
])
def test_invalid_asset_contract_is_rejected(bad_asset):
    with pytest.raises(MusicSfxSupervisionError):
        MusicSfxSupervisor().build(
            episode_id="E1", episode_duration_seconds=10,
            assets=(bad_asset,), cues=(cue("c", "x", "music", 0, 10),),
        )
