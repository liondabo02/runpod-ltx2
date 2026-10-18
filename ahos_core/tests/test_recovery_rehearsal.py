from ahos.recovery_rehearsal import RecoveryRehearsal


def test_recovery_rehearsal_accepts_requeued_interrupted_task():
    before = {
        "heartbeat_state": "error",
        "tasks": [{"task_id": "A", "status": "running"}],
    }
    after = {
        "heartbeat_state": "idle",
        "tasks": [{"task_id": "A", "status": "queued"}],
    }
    report = RecoveryRehearsal().evaluate(before=before, after=after)
    assert report.passed is True
    assert report.recovered_tasks == 1


def test_recovery_rehearsal_rejects_stuck_task():
    report = RecoveryRehearsal().evaluate(
        before={"heartbeat_state": "error", "tasks": [{"task_id": "A", "status": "running"}]},
        after={"heartbeat_state": "error", "tasks": [{"task_id": "A", "status": "running"}]},
    )
    assert report.passed is False
    assert "A:still_unrecoverable" in report.blockers
    assert "heartbeat_not_recovered" in report.blockers
