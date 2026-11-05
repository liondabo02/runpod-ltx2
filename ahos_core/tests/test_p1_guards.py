from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from ahos import live_activity
from ahos.code_work import apply_card_keyboard
from ahos.mission_guard import MissionCancelled
from ahos.owner_console import build_default_console
from ahos.worker_runtime import WorkItem, WorkerExecutionResult


@pytest.fixture(autouse=True)
def _reset_live_activity():
    live_activity.reset_for_tests()
    yield
    live_activity.reset_for_tests()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "www").mkdir(parents=True)
    (root / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "www" / "card-keys.js").write_text("// eski\n", encoding="utf-8")
    return root


def _result(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
    return WorkerExecutionResult(
        task_id=item.task_id,
        worker_id=worker_id,
        success=True,
        summary="ok",
        artifacts=(),
    )


def test_late_executor_cannot_write_after_timeout(tmp_path, monkeypatch) -> None:
    """Timeout sonrası geç kalan executor dosya yazamaz (kooperatif iptal)."""

    monkeypatch.setenv("AHOS_MISSION_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("AHOS_CANCEL_WAIT_SECONDS", "0.2")
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")
    project = _project(tmp_path)
    proceed = threading.Event()
    blocked: list[BaseException] = []

    def slow(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        proceed.wait(5)
        try:
            apply_card_keyboard(project)
        except MissionCancelled as exc:  # beklenen yol
            blocked.append(exc)
            raise
        return _result(item, worker_id)

    started = time.monotonic()
    result = console.run_department_mission(spec, "geç yazma testi", executor=slow)
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    assert result.status in {"blocked", "error"}
    assert "timeout" in result.message.lower()

    proceed.set()
    time.sleep(0.4)

    # Geç kalan iş parçacığı yazmaya çalıştı ama token iptal edildiği için durdu.
    assert blocked, "iptal edilen görev yazma kapısına hiç uğramadı"
    assert (project / "www" / "card-keys.js").read_text(encoding="utf-8") == "// eski\n"
    assert not (project / "www" / "card-keys.js").read_text(encoding="utf-8").count("card-keys")


def test_timeout_or_early_qa_block_is_explicit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_MISSION_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("AHOS_CANCEL_WAIT_SECONDS", "2.0")
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")

    def slow(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        time.sleep(0.4)  # iptal bekleme penceresinde biter
        return _result(item, worker_id)

    result = console.run_department_mission(spec, "iptal doğrulama testi", executor=slow)

    assert result.status in {"blocked", "error"}
    text = (result.message + " " + str(getattr(result, "reason", ""))).lower()
    assert any(mark in text for mark in ("timeout", "doğrulandı", "unverified", "fail-closed"))


def test_duplicate_goal_concurrent_instances_execute_once(tmp_path) -> None:
    """İki bağımsız OwnerConsole aynı görevi aynı anda gönderir: tek çağrı."""

    first = build_default_console(tmp_path)
    second = build_default_console(tmp_path)
    first.handle("çizgi film departmanı kur")
    spec = first.book.require("creative")
    calls: list[str] = []
    release = threading.Event()

    def counting(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        calls.append(item.task_id)
        release.wait(2.0)
        return _result(item, worker_id)

    runner = threading.Thread(
        target=lambda: first.run_department_mission(
            spec, "aynı hedef görevi", executor=counting
        )
    )
    runner.start()
    time.sleep(0.1)

    other = second.run_department_mission(
        spec, "aynı hedef görevi", executor=counting
    )
    release.set()
    runner.join(5)

    missions = {call.split(":")[0] for call in calls}
    assert len(missions) == 1, f"görev {len(missions)} kez yürütüldü: {missions}"
    assert other.status in {"blocked", "completed"}
    assert "executor çağrılmadı" in other.message or "yeniden yürütülmedi" in other.message


def test_write_blocked_while_project_locked_and_no_token(tmp_path) -> None:
    """Kilitli projeye token'sız (alt thread) yazma reddedilir."""

    from ahos import project_locks

    project = _project(tmp_path)
    assert project_locks.acquire(project, mission_id="m-eski") is True
    try:
        with pytest.raises(MissionCancelled):
            apply_card_keyboard(project)
        assert (project / "www" / "card-keys.js").read_text(encoding="utf-8") == "// eski\n"
    finally:
        project_locks.release(project)


def test_second_mission_blocked_while_lock_held(tmp_path) -> None:
    """Kilit tutulurken ikinci görev executor çağırmadan bloke olur."""

    from ahos import project_locks
    from ahos.projects import ProjectLink

    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")
    spec = console.book.require("creative")
    project = _project(tmp_path)
    console.projects.link(
        ProjectLink(
            project_id="p1",
            name="Proje",
            path=project,
            department_id="creative",
        )
    )
    calls: list[str] = []

    def counting(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        calls.append(item.task_id)
        return _result(item, worker_id)

    assert project_locks.acquire(project, mission_id="m-baska") is True
    try:
        result = console.run_department_mission(spec, "kilitli proje görevi", executor=counting)
    finally:
        project_locks.release(project)

    assert calls == [], "kilitli projede executor çağrıldı"
    assert result.status == "blocked"
    assert "proje kilidi" in result.message


def test_restart_does_not_rerun_completed_goal(tmp_path) -> None:
    first = build_default_console(tmp_path)
    first.handle("çizgi film departmanı kur")
    spec = first.book.require("creative")
    calls: list[str] = []

    def counting(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        calls.append(item.task_id)
        return _result(item, worker_id)

    done = first.run_department_mission(spec, "kalıcı hedef", executor=counting)
    # Proje bağlı değil: bağımsız kabul doğrulayıcısı yok → blocked-unverified.
    assert done.status == "blocked"
    assert "blocked-unverified" in done.message or "fail-closed" in done.message
    assert len({c.split(":")[0] for c in calls}) == 1

    # Süreç yeniden başladı: yeni konsol, aynı hedef.
    restarted = build_default_console(tmp_path)
    again = restarted.run_department_mission(
        restarted.book.require("creative"), "kalıcı hedef", executor=counting
    )

    assert len({c.split(":")[0] for c in calls}) == 1, "yeniden başlatma sonrası görev tekrar çalıştı"
    assert ("yeniden yürütülmedi" in again.message) or ("executor çağrılmadı" in again.message)
