from __future__ import annotations

import json

from ahos.outbox import apply_proposal, load_proposals, validate_proposal


def _project(tmp_path):
    root = tmp_path / "proj"
    (root / "www").mkdir(parents=True)
    (root / "www" / "app.js").write_text("const hello = 'Hello';\n", encoding="utf-8")
    return root


def test_valid_patch_is_applied(tmp_path) -> None:
    root = _project(tmp_path)

    result = apply_proposal(
        {
            "task": "selamla",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'Merhaba'"}],
        },
        root,
    )

    assert result["status"] == "applied"
    assert "'Merhaba'" in (root / "www" / "app.js").read_text(encoding="utf-8")


def test_path_outside_project_is_rejected(tmp_path) -> None:
    root = _project(tmp_path)

    edits, problems = validate_proposal(
        {"edits": [{"path": "../evil.js", "content": "x"}]}, root
    )

    assert edits == []
    assert problems and "proje dışı" in problems[0]


def test_missing_find_text_is_reverted(tmp_path) -> None:
    root = _project(tmp_path)

    result = apply_proposal(
        {
            "task": "bozuk",
            "edits": [{"path": "www/app.js", "find": "yok", "replace": "x"}],
        },
        root,
    )

    assert result["status"] == "rejected"
    assert (root / "www" / "app.js").read_text(encoding="utf-8") == "const hello = 'Hello';\n"


def test_failed_verification_is_reverted(tmp_path) -> None:
    root = _project(tmp_path)

    result = apply_proposal(
        {
            "task": "qa",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'X'"}],
        },
        root,
        verify=lambda _root: (False, "tarayıcı hatası"),
    )

    assert result["status"] == "rejected"
    assert "doğrulama" in result["reason"]
    assert "'Hello'" in (root / "www" / "app.js").read_text(encoding="utf-8")


def test_load_proposals_skips_broken_files(tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "a.json").write_text(json.dumps({"task": "a", "edits": []}), encoding="utf-8")
    (outbox / "b.json").write_text("{bozuk", encoding="utf-8")

    records = load_proposals(outbox)

    assert [row["task"] for row in records] == ["a"]
