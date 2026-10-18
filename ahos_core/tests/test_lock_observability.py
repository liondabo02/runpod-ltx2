from __future__ import annotations

from pathlib import Path

from ahos import project_locks


def test_holder_reports_owner_while_locked_and_none_when_free(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    baseline = tmp_path / "noop.json"

    assert project_locks.holder(project) is None

    assert project_locks.acquire(project, mission_id="m-1") is True
    owner = project_locks.holder(project)
    assert owner is not None
    assert owner["mission_id"] == "m-1"
    assert project_locks.probe(project) is True

    assert project_locks.release(project, mission_id="m-1") is True
    assert project_locks.probe(project) is False
    assert project_locks.holder(project) is None
    assert baseline.exists() is False


def test_locked_but_unreadable_metadata_is_unknown_owner(tmp_path, monkeypatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert project_locks.acquire(project, mission_id="m-2") is True

    monkeypatch.setattr(project_locks, "_read_metadata", lambda path: {})
    # Yabancı süreç gibi davran: bu sürecin sahiplik kaydı yok.
    monkeypatch.setattr(project_locks, "_OWNERS", {})

    owner = project_locks.holder(project)
    assert owner is not None
    assert owner["mission_id"] == "unknown-owner"
    project_locks.reset_for_tests()


def test_list_held_only_reports_really_locked_projects(tmp_path) -> None:
    import os

    project = tmp_path / "proj"
    project.mkdir()
    os.environ["AHOS_LOCK_DIR"] = str(tmp_path / "locks")
    try:
        assert project_locks.list_held() == []

        assert project_locks.acquire(project, mission_id="m-held") is True
        held = project_locks.list_held()
        assert [row["mission_id"] for row in held] == ["m-held"]

        assert project_locks.release(project, mission_id="m-held") is True
        assert project_locks.list_held() == []
    finally:
        project_locks.reset_for_tests()


def test_wrong_owner_cannot_release_but_right_owner_can(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert project_locks.acquire(project, mission_id="m-real") is True

    assert project_locks.release(project, mission_id="m-sahte") is False
    assert project_locks.probe(project) is True

    assert project_locks.release(project, mission_id="m-real") is True
    assert project_locks.probe(project) is False


def test_candidate_cannot_swap_acceptance_gate(tmp_path) -> None:
    from ahos.acceptance import trusted_gate

    root = tmp_path / "proj"
    (root / "tools").mkdir(parents=True)
    gate = root / "tools" / "check_offline.py"
    gate.write_text("print('v1')\n", encoding="utf-8")
    baseline = tmp_path / "artifacts" / "acceptance-baseline.json"

    trusted, reason, digest = trusted_gate(root, baseline)
    assert trusted is True and digest

    # Aynı tanım: güvenilir.
    trusted_again, _, _ = trusted_gate(root, baseline)
    assert trusted_again is True

    # Aday kabul testini değiştirdi: fail-closed.
    gate.write_text("print('v2 - always pass')\n", encoding="utf-8")
    tampered, why, _ = trusted_gate(root, baseline)
    assert tampered is False
    assert "değiştirilmiş" in why


def test_missing_acceptance_gate_is_not_trusted(tmp_path) -> None:
    from ahos.acceptance import trusted_gate

    trusted, reason, digest = trusted_gate(tmp_path, tmp_path / "b.json")
    assert trusted is False
    assert "yok" in reason
    assert digest is None
