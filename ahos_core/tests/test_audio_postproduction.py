from pathlib import Path

import pytest

from ahos.audio_postproduction import (
    AudioPostError,
    AudioPostProductionPlanner,
    DialogueTiming,
    export_srt,
)


def line(line_id="L1", speaker="harun", rendered=1.9, start=1.0, end=3.0):
    return DialogueTiming(line_id, speaker, "Merhaba dünya.", start, end, rendered)


def test_complete_post_package_is_deterministic_and_ready():
    planner = AudioPostProductionPlanner()
    first = planner.plan(
        episode_id="S01E001", language="tr", episode_duration_seconds=8,
        dialogue=(line(),), child_speaker_ids=("aden",),
    )
    second = planner.plan(
        episode_id="S01E001", language="tr", episode_duration_seconds=8,
        dialogue=(line(),), child_speaker_ids=("aden",),
    )
    assert first.ready is True
    assert first.package_hash == second.package_hash
    assert {item.stem for item in first.mix_instructions} == {"dialogue", "music", "sfx", "master"}


def test_moderate_adult_mismatch_plans_conservative_time_stretch():
    package = AudioPostProductionPlanner().plan(
        episode_id="E1", language="de", episode_duration_seconds=8,
        dialogue=(line(rendered=2.2),),
    )
    assert package.dub_fits[0].action == "time_stretch"
    assert package.ready is True


def test_child_voice_is_never_automatically_time_stretched():
    package = AudioPostProductionPlanner().plan(
        episode_id="E1", language="tr", episode_duration_seconds=8,
        dialogue=(line(speaker="aden", rendered=2.2),), child_speaker_ids=("aden",),
    )
    assert package.dub_fits[0].action == "rewrite_or_rerecord"
    assert package.qa["child_voice_protected"] is True
    assert package.ready is False


def test_invalid_timeline_and_blank_subtitle_fail_qa():
    item = DialogueTiming("L1", "harun", " ", 7, 9, 1)
    package = AudioPostProductionPlanner().plan(
        episode_id="E1", language="tr", episode_duration_seconds=8, dialogue=(item,),
    )
    assert package.qa["timeline_valid"] is False
    assert package.qa["subtitle_text_complete"] is False
    assert package.ready is False


def test_duplicate_lines_and_empty_input_are_rejected():
    planner = AudioPostProductionPlanner()
    with pytest.raises(AudioPostError, match="at least one"):
        planner.plan(episode_id="E1", language="tr", episode_duration_seconds=8, dialogue=())
    with pytest.raises(AudioPostError, match="duplicate"):
        planner.plan(
            episode_id="E1", language="tr", episode_duration_seconds=8,
            dialogue=(line(), line()),
        )


def test_srt_export_uses_standard_timestamps(tmp_path: Path):
    package = AudioPostProductionPlanner().plan(
        episode_id="E1", language="tr", episode_duration_seconds=8,
        dialogue=(line(start=1.25, end=3.5, rendered=2.2),),
    )
    output = export_srt(package, tmp_path / "episode.tr.srt")
    assert output.read_text(encoding="utf-8") == (
        "1\n00:00:01,250 --> 00:00:03,500\nMerhaba dünya.\n"
    )
