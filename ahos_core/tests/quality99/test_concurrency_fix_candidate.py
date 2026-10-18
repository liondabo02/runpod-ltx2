from ahos_quality99.concurrency_fix_candidate import retry_transient_lock_create


def test_transient_permission_error_is_retried_then_acquired():
    state = {"calls": 0}
    def attempt():
        state["calls"] += 1
        if state["calls"] <= 2:
            raise PermissionError("synthetic Windows contention")
        return True
    report = retry_transient_lock_create(attempt, timeout_seconds=1, poll_seconds=0.001)
    assert report.acquired is True
    assert report.transient_permission_errors == 2
    assert report.attempts == 3


def test_lock_retry_is_bounded():
    report = retry_transient_lock_create(lambda: False, timeout_seconds=0.02, poll_seconds=0.005)
    assert report.acquired is False
    assert report.timed_out is True
