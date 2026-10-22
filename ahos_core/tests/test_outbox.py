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
        require_acceptance=False,
    )

    assert result["status"] == "applied"
    assert "'Merhaba'" in (root / "www" / "app.js").read_text(encoding="utf-8")


def test_missing_acceptance_rejects_by_default(tmp_path) -> None:
    root = _project(tmp_path)

    result = apply_proposal(
        {
            "task": "selamla",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'X'"}],
        },
        root,
    )

    assert result["status"] == "rejected"
    assert "kabul testi" in result["reason"]
    assert "'Hello'" in (root / "www" / "app.js").read_text(encoding="utf-8")


def test_zero_change_patch_is_not_a_delivery(tmp_path) -> None:
    root = _project(tmp_path)

    result = apply_proposal(
        {
            "task": "anlamsız",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'Hello'"}],
        },
        root,
        verify=lambda _root: (True, "geçti"),
    )

    assert result["status"] == "rejected"
    assert "0 dosya" in result["reason"]


def test_stop_file_blocks_everything(tmp_path) -> None:
    root = _project(tmp_path)
    stop = tmp_path / "autonomy.stop"
    stop.write_text("dur", encoding="utf-8")

    result = apply_proposal(
        {
            "task": "selamla",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'X'"}],
        },
        root,
        verify=lambda _root: (True, "geçti"),
        stop_file=stop,
    )

    assert result["status"] == "blocked"
    assert "'Hello'" in (root / "www" / "app.js").read_text(encoding="utf-8")


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


def _gate(root, exit_code: int = 0) -> None:
    (root / "tools").mkdir(exist_ok=True)
    (root / "tools" / "check_offline.py").write_text(
        f"import sys\nsys.exit({exit_code})\n", encoding="utf-8"
    )


def _outbox_with(tmp_path, record: dict):
    outbox = tmp_path / "outbox"
    outbox.mkdir(exist_ok=True)
    (outbox / "p.json").write_text(json.dumps(record), encoding="utf-8")
    return outbox


def test_cli_applies_only_with_acceptance_gate(tmp_path, capsys) -> None:
    from ahos.outbox import main

    root = _project(tmp_path)
    _gate(root, 0)
    outbox = _outbox_with(
        tmp_path,
        {
            "task": "selamla",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'Merhaba'"}],
        },
    )

    code = main(
        ["--dir", str(outbox), "--root", str(root), "--verify", "python tools/check_offline.py"]
    )

    assert code == 0
    assert "'Merhaba'" in (root / "www" / "app.js").read_text(encoding="utf-8")


def test_cli_blocks_when_the_stop_file_exists(tmp_path) -> None:
    from ahos.outbox import main

    root = _project(tmp_path)
    _gate(root, 0)
    outbox = _outbox_with(
        tmp_path,
        {
            "task": "selamla",
            "edits": [{"path": "www/app.js", "find": "'Hello'", "replace": "'X'"}],
        },
    )
    stop = tmp_path / "autonomy.stop"
    stop.write_text("dur", encoding="utf-8")

    code = main(
        [
            "--dir",
            str(outbox),
            "--root",
            str(root),
            "--verify",
            "python tools/check_offline.py",
            "--stop-file",
            str(stop),
        ]
    )

    assert code == 1
    assert "'Hello'" in (root / "www" / "app.js").read_text(encoding="utf-8")
