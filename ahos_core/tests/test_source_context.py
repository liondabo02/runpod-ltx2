from __future__ import annotations

import hashlib

import pytest

from ahos.source_context import select_context, tokens


def _project(tmp_path):
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "node_modules").mkdir()
    (root / "src" / "queue.py").write_text(
        "class TaskQueue:\n    def reserve(self, task):\n        return task\n",
        encoding="utf-8",
    )
    (root / "src" / "ui.js").write_text("const paint = () => 1;\n", encoding="utf-8")
    (root / "tests" / "test_queue.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (root / "node_modules" / "lib.py").write_text("class TaskQueue: pass\n", encoding="utf-8")
    return root


def test_tokens_fold_turkish_characters() -> None:
    assert "kuyruk" in tokens("Kuyruk")
    assert "gorev" in tokens("GÖREV")
    assert "hafiza" in tokens("hafıza")


def test_selects_matching_source_with_hash_and_scope(tmp_path) -> None:
    root = _project(tmp_path)

    result = select_context(root, "kuyruk rezerv görevi")

    paths = [row["path"] for row in result["selected"]]
    assert "src/queue.py" in paths
    assert all(not path.startswith("tests/") for path in paths)
    assert all("node_modules" not in path for path in paths)
    assert result["scan_complete"] is True
    assert "lexical" in result["selection_scope"]
    selected = result["selected"][0]
    assert selected["sha256"] == hashlib.sha256(
        (root / selected["path"]).read_bytes()
    ).hexdigest()
    assert selected["score"] > 0


def test_secret_like_files_are_skipped(tmp_path) -> None:
    root = _project(tmp_path)
    (root / "src" / "credentials_queue.py").write_text(
        "password = 'x'\n", encoding="utf-8"
    )

    result = select_context(root, "kuyruk")

    assert all("credential" not in row["path"] for row in result["selected"])


def test_no_match_is_an_error(tmp_path) -> None:
    root = _project(tmp_path)

    with pytest.raises(ValueError, match="kaynak eşleşmesi yok"):
        select_context(root, "zzzz bilinmeyen konu")


def test_non_utf8_source_is_rejected(tmp_path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "queue.py").write_bytes(b"# kuyruk\n\xff\xfe")

    with pytest.raises(ValueError, match="UTF-8"):
        select_context(root, "kuyruk")


def test_oversized_source_is_rejected(tmp_path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "queue.js").write_text("kuyruk " + "x" * (300 * 1024), encoding="utf-8")

    with pytest.raises(ValueError, match="çok büyük"):
        select_context(root, "kuyruk")


def test_output_is_bounded_to_three_files(tmp_path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    for index in range(6):
        (root / f"queue_{index}.py").write_text("class TaskQueue: pass\n", encoding="utf-8")

    result = select_context(root, "kuyruk")

    assert len(result["selected"]) <= 3


def test_invalid_root_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="geçersiz"):
        select_context(tmp_path / "missing", "kuyruk")
