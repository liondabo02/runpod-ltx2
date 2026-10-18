import pytest
from ahos.department_daemon import run_batch, service_lock


def test_disabled_department_daemon_does_not_call_provider(tmp_path):
    assert run_batch(tmp_path, tmp_path / "missing.json") == {"status": "disabled"}


def test_department_service_lock_is_singleton_and_releases(tmp_path):
    path = tmp_path / "service.lock"
    with service_lock(path):
        with pytest.raises(RuntimeError, match="already running"):
            with service_lock(path):
                pass
    with service_lock(path):
        pass
