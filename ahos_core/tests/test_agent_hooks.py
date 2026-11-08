from __future__ import annotations

import json
from pathlib import Path

from ahos.agent_hooks import post_edit, pre_edit
from ahos.project_memory import (
    MEMORY_FILE,
    default_memory,
    ensure_memory,
    load_memory,
    parse_memory,
)


def test_pre_edit_blocks_android_copy(tmp_path) -> None:
    (tmp_path / "android" / "app").mkdir(parents=True)
    (tmp_path / "android" / "app" / "x.js").write_text("a", encoding="utf-8")

    result = pre_edit("android/app/x.js", root=tmp_path)

    assert result.allowed is False
    assert "kopya" in result.detail


def test_pre_edit_blocks_unknown_suffix(tmp_path) -> None:
    (tmp_path / "a.exe").write_bytes(b"x")

    result = pre_edit("a.exe", root=tmp_path)

    assert result.allowed is False


def test_pre_edit_requires_existing_file(tmp_path) -> None:
    result = pre_edit("yok.js", root=tmp_path)

    assert result.allowed is False
    assert "yok" in result.detail


def test_post_edit_accepts_valid_json(tmp_path) -> None:
    (tmp_path / "a.json").write_text('{"a": 1}', encoding="utf-8")

    assert post_edit("a.json", root=tmp_path).allowed is True


def test_post_edit_rejects_broken_json(tmp_path) -> None:
    (tmp_path / "a.json").write_text('{"a": }', encoding="utf-8")

    assert post_edit("a.json", root=tmp_path).allowed is False


def test_post_edit_rejects_broken_python(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def x(:\n", encoding="utf-8")

    assert post_edit("a.py", root=tmp_path).allowed is False


def test_parse_memory_extracts_sections() -> None:
    text = (
        "# Proje\n## Komutlar\n- test: pytest -q\n- build: npm run build\n"
        "## Kurallar\n- android/ altına yazma\n## Düzen\n- kaynak: `www/`\n"
    )

    memory = parse_memory(text)

    assert memory.commands["test"] == "pytest -q"
    assert memory.commands["build"] == "npm run build"
    assert "android/ altına yazma" in memory.rules
    assert "kaynak: `www/`" in memory.layout


def test_prompt_block_contains_commands_and_rules() -> None:
    memory = parse_memory("## Komutlar\n- test: pytest -q\n## Kurallar\n- kural bir\n")

    block = memory.prompt_block()

    assert "test=pytest -q" in block
    assert "kural bir" in block


def test_ensure_memory_creates_file(tmp_path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}), encoding="utf-8")

    path = ensure_memory(tmp_path)

    assert path.name == MEMORY_FILE
    assert "test: jest" in path.read_text(encoding="utf-8")


def test_default_memory_uses_layout(tmp_path) -> None:
    (tmp_path / "www").mkdir()

    text = default_memory(tmp_path)

    assert "kaynak: `www/`" in text


def test_load_memory_missing_returns_empty(tmp_path) -> None:
    memory = load_memory(tmp_path)

    assert memory.raw == ""
    assert memory.prompt_block() == ""
