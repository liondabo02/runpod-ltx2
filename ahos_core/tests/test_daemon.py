from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from ahos.daemon import AutonomyDaemon, mission_evidence, read_heartbeat
from ahos.delivery import DeliveryTracker, diff_trees, snapshot_tree


class FakeScheduler:
    def __init__(self, statuses: list[str] | None = None) -> None:
        self.statuses = list(statuses or [])
        self.calls = 0
        self.raises: list[Exception] = []
        self.state = SimpleNamespace(
            status="idle",
            hour_key="2026-10-18T12",
            missions_this_hour=0,
            missions_total=0,
            last_reason="",
        )

    def tick(self) -> str:
        self.calls += 1
        if self.raises:
            raise self.raises.pop(0)
        status = self.statuses.pop(0) if self.statuses else "idle"
        self.state.status = status
        return status


def _daemon(tmp_path: Path, scheduler: FakeScheduler, **kwargs) -> AutonomyDaemon:
    options = {"interval_seconds": 5.0, "sleep": lambda _seconds: None}
    options.update(kwargs)
    return AutonomyDaemon(scheduler, tmp_path, **options)


def test_ticks_until_max_ticks_and_writes_heartbeat(tmp_path):
    scheduler = FakeScheduler(["running", "idle", "quota_wait"])
    daemon = _daemon(tmp_path, scheduler, max_ticks=3)

    assert daemon.run() == 0

    assert scheduler.calls == 3
    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["ticks"] == 3
    assert heartbeat["status"] == "stopped"
    assert heartbeat["scheduler"]["last_reason"] == ""
    assert not (tmp_path / "daemon.pid").exists(), "temiz çıkışta pid dosyası silinmeli"


def test_second_instance_is_refused(tmp_path):
    (tmp_path / "daemon.pid").write_text(
        json.dumps({"pid": os.getppid()}), encoding="utf-8"
    )
    scheduler = FakeScheduler()
    daemon = _daemon(tmp_path, scheduler, max_ticks=5)

    assert daemon.run() == 2
    assert scheduler.calls == 0


def test_stop_file_ends_loop_after_current_tick(tmp_path):
    scheduler = FakeScheduler(["running", "running", "running"])

    def sleeper(_seconds: float) -> None:
        (tmp_path / "daemon.stop").write_text("stop", encoding="utf-8")

    daemon = _daemon(tmp_path, scheduler, sleep=sleeper)

    assert daemon.run() == 0
    assert scheduler.calls == 1, "stop dosyası bir sonraki tick'i engellemeli"
    assert read_heartbeat(tmp_path)["status"] == "stopped"


def test_tick_error_does_not_kill_the_loop(tmp_path):
    scheduler = FakeScheduler(["idle", "idle"])
    scheduler.raises = [RuntimeError("görev patladı")]
    daemon = _daemon(tmp_path, scheduler, max_ticks=2)

    assert daemon.run() == 0
    assert scheduler.calls == 3, "patlayan tick sayılmaz; iki başarılı tick için üç çağrı"
    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["ticks"] == 2
    assert heartbeat["status"] == "stopped"


def test_heartbeat_contains_scheduler_quota_snapshot(tmp_path):
    scheduler = FakeScheduler(["running"])
    scheduler.state.missions_this_hour = 2
    scheduler.state.missions_total = 5
    scheduler.state.last_reason = "kota doldu"
    daemon = _daemon(tmp_path, scheduler, max_ticks=1)

    daemon.run()

    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["scheduler"]["missions_this_hour"] == 2
    assert heartbeat["scheduler"]["missions_total"] == 5
    assert heartbeat["scheduler"]["last_reason"] == "kota doldu"


def test_sleep_is_bounded_by_stop_request(tmp_path):
    scheduler = FakeScheduler(["idle", "idle", "idle"])
    daemon = _daemon(tmp_path, scheduler, max_ticks=3)
    slices: list[float] = []

    def sleeper(seconds: float) -> None:
        slices.append(seconds)

    daemon.sleep = sleeper
    daemon.interval_seconds = 12.0
    daemon.run()

    assert slices, "tick'ler arasında uyuma olmalı"
    assert all(0 < value <= 5.0 for value in slices), "uyuma sinyal için parçalanmalı"


def _mission(mission_id: str, changed_files: int, status: str = "routed"):
    step = SimpleNamespace(
        worker_summary=f"varlık denetimi: 89 referans, 0 eksik; {changed_files} dosya değişti"
    )
    return SimpleNamespace(
        status=status,
        mission=SimpleNamespace(mission_id=mission_id, steps=(step,)),
    )


class EvidenceScheduler(FakeScheduler):
    def __init__(self, results: list) -> None:
        super().__init__()
        self.results = list(results)
        self.runner = SimpleNamespace(last_result=None)

    def tick(self) -> str:
        self.calls += 1
        self.runner.last_result = self.results.pop(0)
        return "running"


def test_mission_evidence_reads_changed_file_count():
    evidence = mission_evidence(_mission("m-1", 4))

    assert evidence["mission_id"] == "m-1"
    assert evidence["changed_files"] == 4
    assert evidence["evidence_ok"] is True


def test_three_report_only_missions_pause_the_loop(tmp_path):
    scheduler = EvidenceScheduler([_mission(f"m-{i}", 0) for i in range(1, 4)])
    daemon = _daemon(tmp_path, scheduler, max_ticks=3, no_evidence_limit=3)

    daemon.run()

    assert (tmp_path / "autonomy.pause").exists(), "kanıtsız görevler döngüyü durdurmalı"
    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["no_evidence_streak"] == 3
    assert heartbeat["last_evidence"]["changed_files"] == 0
    assert len((tmp_path / "daemon-missions.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_real_change_resets_no_evidence_streak(tmp_path):
    scheduler = EvidenceScheduler(
        [_mission("m-1", 0), _mission("m-2", 3), _mission("m-3", 0)]
    )
    daemon = _daemon(tmp_path, scheduler, max_ticks=3, no_evidence_limit=2)

    daemon.run()

    assert not (tmp_path / "autonomy.pause").exists()
    assert read_heartbeat(tmp_path)["no_evidence_streak"] == 1


def test_same_mission_is_not_counted_twice(tmp_path):
    same = _mission("m-1", 0)
    scheduler = EvidenceScheduler([same, same])
    daemon = _daemon(tmp_path, scheduler, max_ticks=2, no_evidence_limit=2)

    daemon.run()

    assert not (tmp_path / "autonomy.pause").exists()
    assert read_heartbeat(tmp_path)["no_evidence_streak"] == 1


def test_tree_diff_reports_added_modified_removed(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "gone.txt").write_text("g", encoding="utf-8")
    before = snapshot_tree(root)

    (root / "a.txt").write_text("changed", encoding="utf-8")
    (root / "b.txt").write_text("b", encoding="utf-8")
    (root / "gone.txt").unlink()
    after = snapshot_tree(root)

    delta = diff_trees(before, after)
    assert delta.added == ("b.txt",)
    assert delta.removed == ("gone.txt",)
    assert delta.modified == ("a.txt",)
    assert delta.changed == 3


class WritingScheduler(EvidenceScheduler):
    def __init__(self, results, project) -> None:
        super().__init__(results)
        self.project = project
        self.writes = True

    def tick(self) -> str:
        if self.writes:
            (self.project / f"file-{self.calls}.txt").write_text("x", encoding="utf-8")
        return super().tick()


def test_filesystem_delta_is_authoritative_over_worker_summary(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "index.html").write_text("<html></html>", encoding="utf-8")
    scheduler = WritingScheduler([_mission("m-1", 0)], project)
    daemon = _daemon(
        tmp_path / "rt",
        scheduler,
        max_ticks=1,
        no_evidence_limit=3,
        tracker=DeliveryTracker([project]),
    )

    daemon.run()

    record = json.loads(
        (tmp_path / "rt" / "daemon-missions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert record["source"] == "filesystem"
    assert record["changed_files"] == 1
    assert record["evidence_ok"] is True
    assert "index.html" not in " ".join(record["projects"][0]["modified"])


def test_no_filesystem_change_counts_as_no_evidence(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "index.html").write_text("<html></html>", encoding="utf-8")
    scheduler = WritingScheduler([_mission("m-1", 0)], project)
    scheduler.writes = False
    daemon = _daemon(
        tmp_path / "rt",
        scheduler,
        max_ticks=1,
        no_evidence_limit=1,
        tracker=DeliveryTracker([project]),
    )

    daemon.run()

    record = json.loads(
        (tmp_path / "rt" / "daemon-missions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert record["changed_files"] == 0
    assert record["evidence_ok"] is False
    assert (tmp_path / "rt" / "autonomy.pause").exists()


def test_auto_executor_prefers_model_when_ram_allows(tmp_path, monkeypatch):
    import ahos.daemon as daemon_module

    monkeypatch.setattr(daemon_module, "_model_is_configured", lambda: True)
    scheduler = FakeScheduler()
    daemon = _daemon(
        tmp_path,
        scheduler,
        max_ticks=1,
        executor_mode="auto",
        ram_probe=lambda: 3 * 1024**3,
    )

    daemon.run()

    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["executor_mode"] == "model"
    assert "RAM" in heartbeat["executor_reason"]
    assert os.environ["AHOS_EXECUTOR"] == "model"


def test_auto_executor_falls_back_when_ram_is_low(tmp_path, monkeypatch):
    import ahos.daemon as daemon_module

    monkeypatch.setattr(daemon_module, "_model_is_configured", lambda: True)
    scheduler = FakeScheduler()
    daemon = _daemon(
        tmp_path,
        scheduler,
        max_ticks=1,
        executor_mode="auto",
        ram_probe=lambda: 700 * 1024**2,
    )

    daemon.run()

    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["executor_mode"] == "deterministic"
    assert "<" in heartbeat["executor_reason"]
    assert os.environ["AHOS_EXECUTOR"] == "deterministic"


def test_auto_executor_falls_back_when_model_is_not_configured(tmp_path, monkeypatch):
    import ahos.daemon as daemon_module

    monkeypatch.setattr(daemon_module, "_model_is_configured", lambda: False)
    scheduler = FakeScheduler()
    daemon = _daemon(
        tmp_path,
        scheduler,
        max_ticks=1,
        executor_mode="auto",
        ram_probe=lambda: 8 * 1024**3,
    )

    daemon.run()

    heartbeat = read_heartbeat(tmp_path)
    assert heartbeat["executor_mode"] == "deterministic"
    assert heartbeat["executor_reason"] == "model yapılandırılmadı"


def test_request_stop_ends_the_loop_gracefully(tmp_path):
    scheduler = FakeScheduler(["idle", "idle", "idle"])
    daemon = _daemon(tmp_path, scheduler)

    def sleeper(_seconds: float) -> None:
        daemon.request_stop()

    daemon.sleep = sleeper
    assert daemon.run() == 0
    assert scheduler.calls == 1
    assert read_heartbeat(tmp_path)["status"] == "stopped"


def test_cli_status_reads_the_heartbeat(tmp_path, capsys):
    from ahos.daemon import main

    (tmp_path / "daemon-state.json").write_text(
        json.dumps({"status": "running", "ticks": 7}), encoding="utf-8"
    )

    code = main(["--status", "--runtime-dir", str(tmp_path)])

    assert code == 0
    printed = capsys.readouterr().out
    assert '"ticks": 7' in printed


def test_cli_status_without_heartbeat(tmp_path, capsys):
    from ahos.daemon import main

    assert main(["--status", "--runtime-dir", str(tmp_path)]) == 0
    assert "not-running" in capsys.readouterr().out


def test_forced_model_mode_sets_environment(tmp_path):
    scheduler = FakeScheduler()
    daemon = _daemon(tmp_path, scheduler, max_ticks=1, executor_mode="model")

    daemon.run()

    assert read_heartbeat(tmp_path)["executor_mode"] == "model"
    assert os.environ["AHOS_EXECUTOR"] == "model"


def test_daemon_records_tick_errors_in_the_shared_journal(tmp_path):
    from ahos.errors import ErrorLog

    scheduler = FakeScheduler(["idle"])
    scheduler.raises = [RuntimeError("disk full")]
    daemon = _daemon(tmp_path, scheduler, max_ticks=1)

    daemon.run()

    rows = ErrorLog(tmp_path / "errors.jsonl").recent(5)
    assert len(rows) == 1
    assert rows[0]["source"] == "daemon.tick"
    assert rows[0]["kind"] == "RuntimeError"
    assert "disk full" in rows[0]["message"]
