import json
from dataclasses import asdict

import pytest

from ahos.department_provider import DepartmentProviderConfig, DepartmentProviderError, build_department_generator


def test_department_provider_is_disabled_by_default():
    with pytest.raises(DepartmentProviderError, match="disabled"):
        build_department_generator(DepartmentProviderConfig())


@pytest.mark.parametrize("kwargs", [{"model_id": "paid/model"}, {"timeout_seconds": 0}, {"timeout_seconds": float("nan")}, {"timeout_seconds": 181}, {"allow_external": "false"}])
def test_department_configuration_rejects_paid_and_unbounded_calls(kwargs):
    with pytest.raises(ValueError):
        DepartmentProviderConfig(**kwargs)


def test_department_request_uses_real_transport_free_cap_and_no_serialized_secret(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            assert limit == 2_000_001
            return json.dumps({"choices": [{"message": {"content": '{"artifact":"done"}'}}]}).encode()
    def open_request(request, timeout):
        calls.append((request, timeout))
        return Response()
    monkeypatch.setattr("urllib.request.urlopen", open_request)
    config = DepartmentProviderConfig(allow_external=True, timeout_seconds=12)
    assert build_department_generator(config)("Complete this research \ud800") == '{"artifact":"done"}'
    request, timeout = calls[0]
    body = json.loads(request.data)
    assert timeout == 12
    assert body["provider"]["max_price"] == {"prompt": 0, "completion": 0}
    assert "department employee" in body["messages"][0]["content"]
    assert "test-secret" not in json.dumps(asdict(config))
    assert "test-secret" not in request.data.decode()


def test_provider_failure_is_sanitized_without_retry(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("test-secret")
    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(DepartmentProviderError) as error:
        build_department_generator(DepartmentProviderConfig(allow_external=True))("work")
    assert "test-secret" not in str(error.value)
    assert len(calls) == 1


def test_missing_credential_fails_before_network(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(DepartmentProviderError, match="missing"):
        build_department_generator(DepartmentProviderConfig(allow_external=True))("work")
