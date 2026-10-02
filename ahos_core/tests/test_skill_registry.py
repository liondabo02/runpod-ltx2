from pathlib import Path

import pytest

from ahos.skill_registry import (
    SkillRegistry,
    SkillValidationError,
    discover_skill,
)


def test_skill_registry_discovers_metadata_without_loading_body(tmp_path: Path):
    skill = tmp_path / "audio-qa"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: audio-qa\ndescription: Review generated episode audio.\n---\n"
        "# Audio QA\nSecret body text\n",
        encoding="utf-8",
    )

    registry = SkillRegistry(tmp_path)
    meta = registry.discover_all()[0]

    assert meta.name == "audio-qa"
    assert len(meta.content_hash) == 64
    assert "Secret body text" not in meta.description
    assert "Secret body text" in registry.activate("audio-qa").body


def test_skill_directory_must_match_name(tmp_path: Path):
    skill = tmp_path / "wrong-dir"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: right-name\ndescription: x\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillValidationError):
        discover_skill(skill)
