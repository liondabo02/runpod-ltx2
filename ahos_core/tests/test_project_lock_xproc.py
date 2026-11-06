from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ahos import project_locks
from ahos.code_work import apply_card_keyboard

AHOS_ROOT = Path(__file__).resolve().parents[1]

CHILD = """
import json, sys, time
sys.path.insert(0, {root!r})
from ahos import project_locks
path, owner, hold = sys.argv[1], sys.argv[2], float(sys.argv[3])
ok = project_locks.acquire(path, mission_id=owner)
print(json.dumps({{"ok": ok}}), flush=True)
time.sleep(hold)
"""


@pytest.fixture(autouse=True)
def _clean():
    project_locks.reset_for_tests()
    yield
    project_locks.reset_for_tests()


def _script(tmp_path: Path) -> Path:
    path = tmp_path / "child.py"
    path.write_text(CHILD.format(root=str(AHOS_ROOT)), encoding="utf-8")
    return path


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["AHOS_LOCK_DIR"] = str(tmp_path / "locks")
    return env


def test_two_real_processes_only_one_can_own_project(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    script = _script(tmp_path)
    env = _env(tmp_path)

    first = subprocess.Popen(
        [sys.executable, str(script), str(project), "m-a", "2.0"],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    time.sleep(0.6)
    second = subprocess.run(
        [sys.executable, str(script), str(project), "m-b", "0"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    first_out = first.communicate(timeout=30)[0]

    ok_first = json.loads(first_out.strip().splitlines()[-1])["ok"]
    ok_second = json.loads(second.stdout.strip().splitlines()[-1])["ok"]

    assert [ok_first, ok_second].count(True) == 1, (ok_first, ok_second)


def test_late_writer_blocked_while_other_process_holds_lock(tmp_path) -> None:
    project = tmp_path / "proj"
    (project / "www").mkdir(parents=True)
    (project / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    (project / "www" / "card-keys.js").write_text("// eski\n", encoding="utf-8")
    script = _script(tmp_path)
    env = _env(tmp_path)

    os.environ["AHOS_LOCK_DIR"] = env["AHOS_LOCK_DIR"]
    child = subprocess.Popen(
        [sys.executable, str(script), str(project), "m-other", "2.0"],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    line = child.stdout.readline()
    assert json.loads(line.strip())["ok"] is True
    try:
        from ahos.mission_guard import MissionCancelled

        with pytest.raises(MissionCancelled):
            apply_card_keyboard(project)
        assert (project / "www" / "card-keys.js").read_text(encoding="utf-8") == "// eski\n"
    finally:
        child.communicate(timeout=30)


def test_crashed_owner_releases_lock_and_restart_can_acquire(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    script = _script(tmp_path)
    env = _env(tmp_path)

    child = subprocess.Popen(
        [sys.executable, str(script), str(project), "m-crash", "0.5"],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    child.communicate(timeout=30)

    # Çocuk süreç bitti: OS kilidi serbest, yeni süreç kilidi alabilmeli.
    second = subprocess.run(
        [sys.executable, str(script), str(project), "m-restart", "0"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert json.loads(second.stdout.strip().splitlines()[-1])["ok"] is True


def test_wrong_owner_cannot_release_lock(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    os.environ["AHOS_LOCK_DIR"] = str(tmp_path / "locks")
    try:
        assert project_locks.acquire(project, mission_id="m-real") is True
        assert project_locks.release(project, mission_id="m-sahte") is False
        assert project_locks.probe(project) is True
        assert project_locks.release(project, mission_id="m-real") is True
        assert project_locks.probe(project) is False
    finally:
        project_locks.reset_for_tests()


def test_same_project_in_two_runtimes_uses_same_canonical_lock(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    os.environ["AHOS_LOCK_DIR"] = str(tmp_path / "locks")
    try:
        assert project_locks.acquire(project, mission_id="m-one") is True
        # Farklı bir "panel runtime" aynı canonical projeyi istiyor.
        blocker = project_locks.lock_file(project)
        assert blocker.parent == Path(tmp_path / "locks")
        assert project_locks.acquire(project, mission_id="m-two") is False
    finally:
        project_locks.reset_for_tests()
