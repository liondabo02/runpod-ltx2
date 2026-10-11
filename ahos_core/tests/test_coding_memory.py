from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from ahos.coding_memory import CodingMemory


def event(repository, title="repair source", task_id="TASK", reason="test failed: secret=PRIVATE"):
    task = SimpleNamespace(repository=repository, title=title, task_id=task_id, attempts=1)
    result = SimpleNamespace(approval_file=None, patch_file=None,
                             changed_files=("src/app.py",), reason=reason)
    return task, result


def test_memory_survives_restart_and_scopes_repositories(tmp_path):
    path = tmp_path / "memory.sqlite3"
    first = CodingMemory(path)
    first.record(*event(tmp_path / "repo"), base_commit="abc123")
    recall = CodingMemory(path).context(tmp_path / "repo", "repair")
    assert "acceptance_test_failed" in recall
    assert "abc123" in recall
    assert "PRIVATE" not in path.read_bytes().decode("latin1")
    assert '"task_id": "TASK"' not in first.context(tmp_path / "other", "repair")
    assert "Animation & Cartoon Studio" in recall


def test_memory_redacts_credentials_and_bounds_context(tmp_path):
    memory = CodingMemory(tmp_path / "memory.sqlite3")
    memory.record(*event(tmp_path, title="repair token=PRIVATE sk-FAKEKEY"), base_commit="abc")
    recall = memory.context(tmp_path, "repair", limit=1600)
    assert "PRIVATE" not in recall and "FAKEKEY" not in recall
    assert len(recall) <= 1600
    assert memory.context(tmp_path, "repair", limit=20) == ""


def test_concurrent_memory_writers_preserve_history(tmp_path):
    path = tmp_path / "memory.sqlite3"
    CodingMemory(path)
    def write(index):
        CodingMemory(path).record(*event(tmp_path, task_id=f"TASK-{index}"), base_commit="abc")
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write, range(12)))
    with CodingMemory(path)._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 12


def test_passed_memory_is_not_deployment_proof(tmp_path):
    memory = CodingMemory(tmp_path / "memory.sqlite3")
    patch = tmp_path / "review.patch"
    patch.write_bytes(b"validated patch")
    task, result = event(tmp_path)
    result.patch_file = patch
    result.approval_file = tmp_path / "approval.json"
    memory.record(task, result, base_commit="abc")
    recall = memory.context(tmp_path, "repair")
    assert "tests_passed_waiting_owner" in recall
    assert "does not mean merged, deployed or owner approved" in recall
    assert "patch_sha256" in recall
