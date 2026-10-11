from __future__ import annotations

import subprocess
import sys
import time
import json
from pathlib import Path

import pytest

from ahos.coding_supervisor import (
    CodingSupervisor,
    CodingSupervisorStore,
    CodingTaskStatus,
    _run_builder_command,
    main,
)
from ahos.coding_worker import AutonomousCodingWorker, CodingBacklogItem


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
    return repo


def _item(repo: Path, task_id: str = "CODE-1") -> CodingBacklogItem:
    return CodingBacklogItem(
        task_id=task_id, title="safe edit", repository=repo,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "assert True"),),
    )


def _allow_python(command) -> bool:
    return tuple(command[:1]) == (sys.executable,)


def test_restarted_supervisor_recalls_prior_failed_task(tmp_path):
    repo = _repo(tmp_path)
    queue = tmp_path / "queue.json"
    store = CodingSupervisorStore(queue)
    store.enqueue(CodingBacklogItem("OLD", "repair value", repo, allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "assert False"),)), max_attempts=1)
    def edit(prompt, worktree):
        (worktree / "src/app.py").write_text("VALUE = 2\n", encoding="utf-8")
    supervisor = CodingSupervisor(store=store,
        worker=AutonomousCodingWorker(runner=edit, workspace_root=tmp_path / "workers"),
        worker_id="agy", test_command_policy=_allow_python)
    assert supervisor.run_once().status is CodingTaskStatus.RETRIES_EXHAUSTED
    store.enqueue(_item(repo, "NEW"))
    def remembered_edit(prompt, worktree):
        assert '"task_id": "OLD"' in prompt
        assert "acceptance_test_failed" in prompt
        assert "Animation & Cartoon Studio" in prompt
        edit(prompt, worktree)
    restarted = CodingSupervisor(store=CodingSupervisorStore(queue),
        worker=AutonomousCodingWorker(runner=remembered_edit, workspace_root=tmp_path / "workers"),
        worker_id="agy", test_command_policy=_allow_python)
    assert restarted.run_once().status is CodingTaskStatus.WAITING_OWNER_APPROVAL
    assert queue.with_suffix(".memory.sqlite3").is_file()


def test_builder_process_uses_utf8_for_turkish_task_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    _run_builder_command(["builder"], "sağlık ışığı", tmp_path)

    assert captured["input"] == "sağlık ışığı"
    assert captured["text"] is True
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_supervisor_persists_idempotent_task_and_stops_at_owner_gate(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    item = _item(repo)
    first = store.enqueue(item, idempotency_key="issue:7", max_attempts=2)
    assert store.enqueue(item, idempotency_key="issue:7", max_attempts=2) == first

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    supervisor = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="supervisor-1", test_command_policy=_allow_python,
    )
    result = supervisor.run_once()
    assert result and result.status is CodingTaskStatus.WAITING_OWNER_APPROVAL
    assert result.attempts == 1
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout == ""
    approved = store.record_owner_decision(item.task_id, approved=True)
    assert approved.status is CodingTaskStatus.OWNER_APPROVED
    assert subprocess.run(["git", "log", "-1", "--format=%s"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip() == "initial"


def test_idempotency_key_rejects_different_payload(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), idempotency_key="same")
    with pytest.raises(ValueError, match="different task payload"):
        store.enqueue(_item(repo, "CODE-2"), idempotency_key="same")


def test_bounded_retries_and_policy_is_fail_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), max_attempts=2)
    worker = AutonomousCodingWorker(runner=lambda *_: None, workspace_root=tmp_path / "workers")
    supervisor = CodingSupervisor(store=store, worker=worker, worker_id="s")
    assert supervisor.run_once().status is CodingTaskStatus.QUEUED
    assert supervisor.run_once().status is CodingTaskStatus.RETRIES_EXHAUSTED
    assert store.get("CODE-1").attempts == 2


def test_automatic_retry_receives_previous_failure_diagnostic(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), max_attempts=2)
    prompts: list[str] = []

    def builder(prompt: str, _worktree: Path):
        prompts.append(prompt)

    supervisor = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="s", test_command_policy=_allow_python,
    )

    assert supervisor.run_once().status is CodingTaskStatus.QUEUED
    assert supervisor.run_once().status is CodingTaskStatus.RETRIES_EXHAUSTED
    assert "Previous attempt failed the deterministic gate" not in prompts[0]
    assert "Previous attempt failed the deterministic gate" in prompts[1]
    assert "worker produced no tracked changes" in prompts[1]
    assert "Preserve the full task scope and existing capabilities" in prompts[1]
    assert "Repair strategy:" in prompts[1]


def test_repair_strategy_escalates_without_reducing_feature_scope() -> None:
    assert "repair the diagnosed defect" in CodingSupervisor._repair_strategy(2)
    assert "integrate it additively" in CodingSupervisor._repair_strategy(3)
    final = CodingSupervisor._repair_strategy(4)
    assert "different compatible solution" in final
    assert "targeted tests before the full suite" in final


def test_automatic_retry_receives_previous_candidate_source(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    item = CodingBacklogItem(
        task_id="CODE-REPAIR", title="repair candidate", repository=repo,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "raise SystemExit('gate failure')"),),
    )
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(item, max_attempts=2)
    prompts: list[str] = []

    def builder(prompt: str, worktree: Path):
        prompts.append(prompt)
        (worktree / "src" / "app.py").write_text(
            "VALUE = 'candidate needing repair'\n", encoding="utf-8"
        )

    supervisor = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="s", test_command_policy=_allow_python,
    )

    assert supervisor.run_once().status is CodingTaskStatus.QUEUED
    assert supervisor.run_once().status is CodingTaskStatus.RETRIES_EXHAUSTED
    assert "Previous candidate source follows" in prompts[1]
    assert "candidate needing repair" in prompts[1]


def test_owner_can_explicitly_retry_an_exhausted_task(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), max_attempts=1)
    claimed = store.claim("worker")
    store.finish(claimed.task_id, "worker", success=False, reason="temporary failure")

    retried = store.retry("CODE-1")

    assert retried.status is CodingTaskStatus.QUEUED
    assert retried.attempts == 0
    assert retried.max_attempts == 4
    assert retried.last_error == "temporary failure"


def test_owner_retry_uses_a_fresh_workspace_when_old_attempt_remains(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), max_attempts=1)
    first = store.claim("worker")
    store.finish(first.task_id, "worker", success=False, reason="temporary failure")
    store.retry("CODE-1")
    stale = tmp_path / "workers" / "CODE-1" / "attempt-1" / "CODE-1"
    stale.mkdir(parents=True)

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="worker",
        test_command_policy=_allow_python,
    ).run_once()

    assert result.status is CodingTaskStatus.WAITING_OWNER_APPROVAL
    assert Path(result.worktree) != stale


def test_retry_cli_requeues_exhausted_task(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    queue = tmp_path / "queue.json"
    store = CodingSupervisorStore(queue)
    store.enqueue(_item(repo), max_attempts=1)
    claimed = store.claim("worker")
    store.finish(claimed.task_id, "worker", success=False, reason="temporary failure")
    monkeypatch.setattr(sys, "argv", [
        "ahos.coding_supervisor", "--queue", str(queue), "retry",
        "--task-id", "CODE-1",
    ])

    assert main() == 0
    assert store.get("CODE-1").status is CodingTaskStatus.QUEUED


def test_owner_decision_rejects_modified_patch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo))

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = CodingSupervisor(
        store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers"),
        worker_id="s", test_command_policy=_allow_python,
    ).run_once()
    Path(result.patch_file).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="patch was modified"):
        store.record_owner_decision("CODE-1", approved=True)


def test_worker_rechecks_scope_after_tests(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "protected.txt").write_text("safe\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "protected"], cwd=repo, check=True)
    item = CodingBacklogItem(
        task_id="MUTATE", title="test mutation", repository=repo,
        allowed_paths=("src",),
        test_commands=((sys.executable, "-c", "from pathlib import Path; Path('protected.txt').write_text('bad')"),),
    )

    def builder(_prompt: str, worktree: Path):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    result = AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers").run(item, "s")
    assert result.status.value == "blocked"
    assert "tests changed files outside approved scope" in result.reason


def test_store_recovers_abandoned_stale_lock(tmp_path: Path) -> None:
    store = CodingSupervisorStore(tmp_path / "queue.json", lock_timeout_seconds=0.2,
                                  stale_lock_seconds=0.01)
    store.lock_path.write_text("dead-process\n", encoding="ascii")
    time.sleep(0.02)
    assert store.status()["counts"]["queued"] == 0
    assert not store.lock_path.exists()


def test_enqueue_cli_accepts_windows_utf8_bom(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "task_id": "WINDOWS-BOM",
        "title": "accept PowerShell JSON",
        "repository": str(repo),
        "allowed_paths": ["src"],
        "test_commands": [],
    }), encoding="utf-8-sig")
    queue = tmp_path / "queue.json"
    monkeypatch.setattr(sys, "argv", [
        "ahos.coding_supervisor", "--queue", str(queue), "enqueue",
        "--task-json", str(task),
    ])

    assert main() == 0
    assert CodingSupervisorStore(queue).get("WINDOWS-BOM").status is CodingTaskStatus.QUEUED


def test_run_once_cli_accepts_builder_argv_with_nested_options(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", [
        "ahos.coding_supervisor", "--queue", str(tmp_path / "queue.json"), "run-once",
        "--workspace", str(tmp_path / "workers"), "--worker-id", "dev-01",
        "--builder-command-json",
        json.dumps([sys.executable, "-m", "builder", "--model", "openrouter/free"]),
        "--allow-test-executable", sys.executable,
    ])

    assert main() == 0


def test_run_once_cli_records_builder_stderr(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    queue = tmp_path / "queue.json"
    store = CodingSupervisorStore(queue)
    store.enqueue(_item(repo), max_attempts=2)
    monkeypatch.setattr(sys, "argv", [
        "ahos.coding_supervisor", "--queue", str(queue), "run-once",
        "--workspace", str(tmp_path / "workers"), "--worker-id", "dev-01",
        "--builder-command-json", json.dumps([
            sys.executable, "-c",
            "import sys; sys.stderr.write('builder diagnostic detail'); raise SystemExit(7)",
        ]),
        "--allow-test-executable", sys.executable,
    ])

    assert main() == 2
    record = store.get("CODE-1")
    assert record.status is CodingTaskStatus.QUEUED
    assert "builder diagnostic detail" in record.last_error


def test_provider_wait_survives_restart_blocks_other_tasks_and_resumes(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    monkeypatch.setattr('ahos.coding_supervisor._now', lambda: now)
    store = CodingSupervisorStore(tmp_path / 'queue.json')
    repo = _repo(tmp_path)
    store.enqueue(_item(repo), max_attempts=1)
    claimed = store.claim('w')
    waiting = store.defer_provider(claimed.task_id, 'w', 900)
    assert waiting.attempts == 0
    assert waiting.status is CodingTaskStatus.WAITING_PROVIDER
    store = CodingSupervisorStore(store.path)
    store.enqueue(_item(repo, 'CODE-2'))
    assert store.claim('w') is None
    now += timedelta(seconds=901)
    reclaimed = store.claim('w')
    assert reclaimed.task_id == 'CODE-1'
    assert reclaimed.attempts == 1
    waiting = store.defer_provider('CODE-1', 'w')
    assert waiting.provider_waits == 2
    assert datetime.fromisoformat(waiting.next_retry_at) == now + timedelta(seconds=600)


def test_legacy_provider_recovery_preserves_real_failures(tmp_path):
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / 'queue.json')
    for task_id, reason in [('RATE', 'supervisor caught RuntimeError: builder exited with 1: CodingBuilderError: HTTP 429'), ('CODE', 'worker produced no tracked changes')]:
        store.enqueue(_item(repo, task_id), max_attempts=1)
        store.claim('w')
        store.finish(task_id, 'w', success=False, reason=reason)
    assert store.recover_provider_failures() == 1
    assert store.get('RATE').status is CodingTaskStatus.WAITING_PROVIDER
    assert store.get('CODE').status is CodingTaskStatus.RETRIES_EXHAUSTED
    assert store.recover_provider_failures() == 0


def test_supervisor_defers_typed_provider_failure(tmp_path):
    from ahos.coding_supervisor import CodingProviderDeferred
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / 'queue.json')
    store.enqueue(_item(repo), max_attempts=1)
    def builder(*args):
        raise CodingProviderDeferred(300)
    supervisor = CodingSupervisor(store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / 'workers'),
        worker_id='w', test_command_policy=lambda command: True)
    result = supervisor.run_once()
    assert result.status is CodingTaskStatus.WAITING_PROVIDER
    assert result.attempts == 0


def test_cli_transports_provider_wait_without_traceback_retry(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path)
    queue = tmp_path / 'queue.json'
    store = CodingSupervisorStore(queue)
    store.enqueue(_item(repo), max_attempts=1)
    monkeypatch.setattr('ahos.coding_supervisor._run_builder_command',
        lambda *args: subprocess.CompletedProcess([], 75, stdout='', stderr='AHOS_PROVIDER_WAIT:429:900\n'))
    monkeypatch.setattr(sys, 'argv', ['supervisor', '--queue', str(queue), 'run-once',
        '--workspace', str(tmp_path / 'workers'), '--worker-id', 'w',
        '--builder-command-json', '["builder"]', '--allow-test-executable', sys.executable])
    main()
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'waiting_provider'
    assert result['attempts'] == 0
    assert result['provider_waits'] == 1


def test_queue_save_retries_transient_windows_sharing_error(tmp_path, monkeypatch):
    import ahos.coding_supervisor as module

    store = CodingSupervisorStore(tmp_path / "queue.json")
    store._save({})
    original_replace = module._replace_queue_file
    calls = []

    def busy_once(source, destination):
        calls.append(1)
        if len(calls) == 1:
            error = PermissionError("sharing violation")
            error.winerror = 32
            raise error
        original_replace(source, destination)

    monkeypatch.setattr(module, "_replace_queue_file", busy_once)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    store._save({})
    assert len(calls) == 2
    assert json.loads(store.path.read_text()) == {}
    assert not list(tmp_path.glob("*.tmp"))


def test_queue_failed_atomic_save_preserves_previous_json_and_cleans_temp(tmp_path, monkeypatch):
    import ahos.coding_supervisor as module

    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.path.write_text('{"previous": true}\n')
    previous = store.path.read_bytes()

    def denied(_source, _destination):
        raise PermissionError("permission denied")

    monkeypatch.setattr(module, "_replace_queue_file", denied)
    with pytest.raises(PermissionError):
        store._save({})
    assert store.path.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


def test_existing_windows_queue_uses_replacefile_api(tmp_path, monkeypatch):
    import ctypes
    from types import SimpleNamespace
    import ahos.coding_supervisor as module

    destination = tmp_path / "queue.json"
    source = tmp_path / "queue.tmp"
    destination.write_text("old")
    source.write_text("new")
    calls = []

    class ReplaceFile:
        def __call__(self, *args):
            calls.append(args)
            return True

    api = ReplaceFile()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: SimpleNamespace(ReplaceFileW=api), raising=False)
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    module._replace_queue_file(source, destination)
    assert calls == [(str(destination.resolve()), str(source.resolve()), None, 0, None, None)]


def test_queue_windows_sharing_retry_is_bounded(tmp_path, monkeypatch):
    import ahos.coding_supervisor as module

    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.path.write_text('{}\n')
    previous = store.path.read_bytes()
    clock = iter((0.0, 0.5, 2.0))
    calls = []

    def locked(_source, _destination):
        calls.append(1)
        error = PermissionError("sharing violation")
        error.winerror = 32
        raise error

    monkeypatch.setattr(module, "_replace_queue_file", locked)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    with pytest.raises(PermissionError):
        store._save({})
    assert len(calls) == 2
    assert store.path.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


def test_supervisor_preserves_task_scoped_executor_across_attempts(tmp_path):
    repo = _repo(tmp_path)
    store = CodingSupervisorStore(tmp_path / "queue.json")
    store.enqueue(_item(repo), max_attempts=2)
    items = []
    class Executor:
        execution_mode = "docker"
        def __call__(self, worktree, command):
            return subprocess.CompletedProcess(command, 1 if len(items) == 1 else 0, "", "failed")
    def factory(item):
        items.append(item)
        return Executor()
    def builder(_prompt, worktree):
        (worktree / "src" / "app.py").write_text("VALUE = 2\n")
    supervisor = CodingSupervisor(store=store,
        worker=AutonomousCodingWorker(runner=builder, workspace_root=tmp_path / "workers", test_executor_factory=factory),
        worker_id="s", test_command_policy=_allow_python)
    assert supervisor.run_once().status is CodingTaskStatus.QUEUED
    result = supervisor.run_once()
    assert result.status is CodingTaskStatus.WAITING_OWNER_APPROVAL
    assert [item.allowed_paths for item in items] == [("src",), ("src",)]
    assert json.loads(Path(result.approval_file).read_text())["test_execution_mode"] == "docker"


def test_hot_sandbox_config_accepts_bom_and_observes_updates(tmp_path):
    from ahos.coding_supervisor import _hot_sandbox_config
    queue = tmp_path / "queue.json"
    assert _hot_sandbox_config(queue) == (None, 300)
    path = tmp_path / "company-service-config.json"
    image = "sha256:" + "a" * 64
    path.write_text(json.dumps({"coding_supervisor": {"enabled": True, "sandbox_image": image, "sandbox_timeout_seconds": 600}, "unrelated": {"builder_command": ["ignored"]}}), encoding="utf-8-sig")
    assert _hot_sandbox_config(queue) == (image, 600)
    path.write_text(json.dumps({"coding_supervisor": {"enabled": False, "sandbox_image": image}}))
    assert _hot_sandbox_config(queue) == (None, 300)


@pytest.mark.parametrize("config", [[], {"coding_supervisor": []}, {"coding_supervisor": {"enabled": "true"}},
    {"coding_supervisor": {"enabled": True, "sandbox_image": "latest"}},
    {"coding_supervisor": {"enabled": True, "sandbox_image": "sha256:" + "a" * 64, "sandbox_timeout_seconds": True}}])
def test_hot_sandbox_config_fails_closed_for_invalid_settings(tmp_path, config):
    from ahos.coding_supervisor import _hot_sandbox_config
    (tmp_path / "company-service-config.json").write_text(json.dumps(config))
    with pytest.raises(ValueError):
        _hot_sandbox_config(tmp_path / "queue.json")


def test_run_once_reads_sandbox_config_without_daemon_restart(tmp_path, monkeypatch):
    import ahos.docker_test_executor as sandbox
    image = "sha256:" + "b" * 64
    (tmp_path / "company-service-config.json").write_text(json.dumps({"coding_supervisor": {"enabled": True, "sandbox_image": image, "sandbox_timeout_seconds": 400}}))
    calls = []
    class Executor:
        def __init__(self, image, timeout_seconds, allowed_paths=()):
            calls.append((image, timeout_seconds, allowed_paths))
    def no_task(supervisor):
        supervisor.worker.test_executor_factory(_item(tmp_path))
        return None
    monkeypatch.setattr(sandbox, "DockerTestExecutor", Executor)
    monkeypatch.setattr(CodingSupervisor, "run_once", no_task)
    monkeypatch.setattr(sys, "argv", ["supervisor", "--queue", str(tmp_path / "queue.json"), "run-once", "--workspace", str(tmp_path / "workers"), "--worker-id", "w", "--builder-command-json", '["builder"]', "--allow-test-executable", sys.executable])
    assert main() == 0
    assert calls[-1] == (image, 400, ("src",))
