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
