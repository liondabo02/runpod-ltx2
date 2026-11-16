"""Studio skill kataloğu: profesyonel prosedürler yüklenir ve aranır."""
from __future__ import annotations

from pathlib import Path

from ahos.studio_skills import find_skill, load_skills, main, search_skills

ROOT = Path(__file__).resolve().parents[2]


def test_studio_skills_are_loaded():
    skills = load_skills()
    names = {skill.name for skill in skills}
    assert {
        "studio-character-rig",
        "studio-voice-lipsync",
        "studio-cinematic-video",
        "studio-longform-production",
        "studio-media-qa",
        "studio-provider-integration",
    } <= names
    for skill in skills:
        assert skill.description.strip()
        assert skill.body.strip()
        assert (ROOT / skill.path).is_file()


def test_studio_skills_are_searchable_and_showable():
    hits = search_skills("lip-sync")
    assert any(skill.name == "studio-voice-lipsync" for skill in hits)
    skill = find_skill("studio-character-rig")
    assert skill is not None and "rig" in skill.body.casefold()
    assert find_skill("does-not-exist") is None


def test_skill_cli_lists_catalog(capsys):
    assert main(["--list"]) == 0
    output = capsys.readouterr().out
    assert "studio-character-rig" in output
    assert "studio-media-qa" in output
