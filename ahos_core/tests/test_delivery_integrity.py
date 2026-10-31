"""Content-backed proof: file metadata and narrative are not delivery evidence."""

from __future__ import annotations

import os

from ahos.delivery import DeliveryTracker, diff_trees, snapshot_tree


def test_equal_size_equal_mtime_edit_is_detected_by_hash(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    path = project / "app.js"
    path.write_text("abc\n", encoding="utf-8")
    before = snapshot_tree(project)
    old_mtime = path.stat().st_mtime_ns

    path.write_text("xyz\n", encoding="utf-8")
    os.utime(path, ns=(path.stat().st_atime_ns, old_mtime))
    after = snapshot_tree(project)
    assert before.files == after.files, "metadata alone cannot prove the edit"

    diff = diff_trees(before, after)
    assert diff.modified == ("app.js",)
    assert diff.changed == 1
    assert not diff.unverified


def test_touch_without_content_change_does_not_count(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    path = project / "app.py"
    path.write_text("print(1)\n", encoding="utf-8")
    before = snapshot_tree(project)

    os.utime(path, None)
    after = snapshot_tree(project)
    diff = diff_trees(before, after)
    assert diff.changed == 0
    assert diff.modified == ()


def test_truncated_snapshot_cannot_claim_success(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "a.py").write_text("a", encoding="utf-8")
    before = snapshot_tree(root, max_files=1)

    (root / "b.py").write_text("new", encoding="utf-8")
    after = snapshot_tree(root, max_files=1)
    assert after.truncated

    diff = diff_trees(before, after)
    assert diff.unverified
    assert diff.changed == 0
    assert diff.to_dict()["unverified"] is True


def test_missing_project_root_fails_closed(tmp_path):
    missing = tmp_path / "not-created"
    initial = snapshot_tree(missing)
    assert initial.truncated
    missing.mkdir()
    (missing / "new.py").write_text("hello", encoding="utf-8")
    diff = diff_trees(initial, snapshot_tree(missing))
    assert diff.changed == 0
    assert diff.unverified


def test_tracker_rejects_volatile_only_updates(tmp_path):
    root = tmp_path / "project"
    (root / "data").mkdir(parents=True)
    (root / "data" / "runtime.json").write_text("{}", encoding="utf-8")
    before = DeliveryTracker([root]).snapshot()
    (root / "data" / "runtime.json").write_text('{"success":true}', encoding="utf-8")
    after = DeliveryTracker([root]).snapshot()
    verdict = DeliveryTracker([root]).diff(before, after)
    assert verdict["changed_files"] == 0
