import json
from pathlib import PurePosixPath, Path
import subprocess
import pytest
from ahos import antigravity_coding_builder as builder


def test_proposal_uses_empty_workspace_and_hides_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "PRIVATE_TEST_KEY")
    def run(args, **kwargs):
        assert "--sandbox" in args
        assert args[args.index("--mode") + 1] == "plan"
        assert Path(kwargs["cwd"]).exists()
        assert list(Path(kwargs["cwd"]).iterdir()) == []
        assert "OPENROUTER_API_KEY" not in kwargs["env"]
        return subprocess.CompletedProcess(args, 0, json.dumps({"status": "SUCCESS", "response": "{}"}), "")
    monkeypatch.setattr(builder.subprocess, "run", run)
    assert builder.proposal("agy", "public task", 10) == "{}"


def test_provider_stderr_is_not_exposed(monkeypatch):
    monkeypatch.setattr(builder.subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess(a, 1, "", "PRIVATE_TEST_KEY"))
    with pytest.raises(builder.CodingBuilderError) as error:
        builder.proposal("agy", "public task", 10)
    assert "PRIVATE_TEST_KEY" not in str(error.value)


def test_invalid_then_repaired_proposal_preserves_task_and_applies(tmp_path, monkeypatch):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "src/app.py"], cwd=tmp_path, check=True)
    replies = iter([
        {"files": [{"path": "outside.py", "content": "bad"}]},
        {"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]},
    ])
    calls = []
    def propose(command, prompt, timeout):
        calls.append(prompt)
        assert "ENTIRE ORIGINAL TASK" in prompt
        assert target.read_text() == "VALUE = 1\n"
        return json.dumps(next(replies))
    monkeypatch.setattr(builder, "proposal", propose)
    result = builder.request_edits("ENTIRE ORIGINAL TASK", tmp_path,
        (PurePosixPath("src"),), command="agy")
    assert "scope:" in calls[1]
    assert not (tmp_path / "outside.py").exists()
    builder.apply_response(tmp_path, (PurePosixPath("src"),), result)
    assert target.read_text() == "VALUE = 2\n"


def test_transport_budget_never_truncates_task(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "proposal", lambda *a: pytest.fail("must not send truncated task"))
    with pytest.raises(builder.CodingBuilderError, match="not truncated"):
        builder.request_edits("X" * 29000, tmp_path, (PurePosixPath("src"),), command="agy")


def test_exact_search_repair_receives_current_source(tmp_path, monkeypatch):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    calls = []
    def propose(command, prompt, timeout):
        calls.append(prompt)
        search = "VALUE = 99" if len(calls) == 1 else "VALUE = 1"
        return json.dumps({"edits": [{"path": "src/app.py", "search": search, "replace": "VALUE = 2"}]})
    monkeypatch.setattr(builder, "proposal", propose)
    result = builder.request_edits("Fix VALUE correctly", tmp_path, (PurePosixPath("src"),), command="agy")
    assert "Actual file: src/app.py; search matches: 0" in calls[1]
    assert "Unique current-source search candidate" in calls[1]
    assert "src/app.py" in calls[0]
    assert target.read_text() == "VALUE = 1\n"
    builder.apply_response(tmp_path, (PurePosixPath("src"),), result)
    assert target.read_text() == "VALUE = 2\n"


def test_long_task_is_preserved_while_context_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "_file_inventory", lambda *a: "src/app.py\n" * 2000)
    monkeypatch.setattr(builder, "_local_context", lambda *a: "SOURCE" * 10000)
    task = "TASK START " + "x" * 22000 + " TASK END"
    calls = []
    def propose(command, prompt, timeout):
        calls.append(prompt)
        return json.dumps({"files": [{"path": "src/new.py", "content": "VALUE = 2\n"}]})
    monkeypatch.setattr(builder, "proposal", propose)
    builder.request_edits(task, tmp_path, (PurePosixPath("src"),), command="agy")
    assert task in calls[0]
    assert len(calls[0]) <= builder.TRANSPORT_CHARS
    assert "Data excerpt only" in calls[0]


@pytest.mark.parametrize("attempts,timeout", [(0, 180), (4, 180), (2, 0), (2, 601)])
def test_invalid_limits_never_call_provider(tmp_path, monkeypatch, attempts, timeout):
    monkeypatch.setattr(builder, "proposal", lambda *a: pytest.fail("invalid request"))
    with pytest.raises(builder.CodingBuilderError, match="requires"):
        builder.request_edits("task", tmp_path, (PurePosixPath("src"),),
                              command="agy", attempts=attempts, timeout=timeout)


@pytest.mark.parametrize("expected,approved", [(2, True), (3, False)])
def test_antigravity_adapter_to_worker_acceptance(tmp_path, monkeypatch, expected, approved):
    import sys
    from ahos.coding_worker import AutonomousCodingWorker, CodingBacklogItem, CodingWorkerStatus
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
    for command in (["git", "init", "-q"], ["git", "add", "."],
                    ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "-qm", "initial"]):
        subprocess.run(command, cwd=repo, check=True)
    def propose(command, prompt, timeout):
        assert "Acceptance test argv" in prompt
        return json.dumps({"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]})
    monkeypatch.setattr(builder, "proposal", propose)
    def run(prompt, worktree):
        roots = builder._allowed_paths(prompt)
        result = builder.request_edits(prompt, worktree, roots, command="agy")
        builder.apply_response(worktree, roots, result)
    item = CodingBacklogItem("AGY-ACCEPT", "Update VALUE", repo, allowed_paths=("src",),
        test_commands=((sys.executable, "-c", f"from src.app import VALUE; assert VALUE == {expected}"),))
    result = AutonomousCodingWorker(runner=run, workspace_root=tmp_path / "workers").run(item, "agy")
    assert (result.status is CodingWorkerStatus.WAITING_OWNER_APPROVAL) is approved
    assert (result.patch_file is not None) is approved
    assert (repo / "src/app.py").read_text() == "VALUE = 1\n"
