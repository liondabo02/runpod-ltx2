from ahos.technology_radar import RadarStatus, studio_technology_radar


def test_radar_contains_adopted_skill_standard_and_runpod():
    entries = {entry.technology_id: entry for entry in studio_technology_radar()}
    assert entries["agent-skills-open-standard"].status is RadarStatus.ADOPT
    assert entries["runpod-serverless"].status is RadarStatus.ADOPT


def test_noncommercial_models_are_not_commercial_defaults():
    entries = {entry.technology_id: entry for entry in studio_technology_radar()}
    assert entries["f5-tts"].commercial_default is False
    assert entries["fish-speech-s2"].commercial_default is False
