from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _script(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8-sig")


def test_autopilot_reserves_budget_before_enqueueing_paid_task() -> None:
    script = _script("Holding-Autopilot-Loop.ps1")
    reserve = script.index("Reserve-Cost $PaidTaskReserveUsd")
    enqueue = script.index("$WorkerExe enqueue")
    assert reserve < enqueue
    assert "keep the reservation when the provider does not report a cost" in script


def test_autopilot_accepts_planner_created_tasks() -> None:
    script = _script("Holding-Autopilot-Loop.ps1")
    assert "$_.status -in @('pending', 'planned')" in script


def test_launcher_forwards_paid_task_reserve() -> None:
    script = _script("Start-Holding-Autopilot.ps1")
    assert "[decimal]$PaidTaskReserveUsd = 0.08" in script
    assert "'-PaidTaskReserveUsd', [string]$PaidTaskReserveUsd" in script


def test_status_collapses_poll_noise_and_filters_sdk_banner() -> None:
    script = _script("Status-Holding-Autopilot.ps1")
    assert "repeated $($statusLines.Count)x" in script
    assert "AUTOPILOT ERROR|ERROR:|Traceback|Exception" in script
