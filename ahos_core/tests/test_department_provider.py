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


@pytest.mark.parametrize("header, expected", [("120", 120), ("0", 60), ("nan", 300), ("invalid", 300), ("999999", 86400)])
def test_429_preserves_only_safe_status_and_bounded_retry_header(monkeypatch, header, expected):
    from urllib.error import HTTPError
    from ahos.department_provider import DepartmentRateLimited
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    def fail(*args, **kwargs):
        raise HTTPError("https://provider", 429, "test-secret", {"Retry-After": header}, None)
    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(DepartmentRateLimited) as error:
        build_department_generator(DepartmentProviderConfig(allow_external=True))("work")
    assert error.value.retry_after_seconds == expected
    assert "429" in str(error.value)
    assert "test-secret" not in str(error.value)


def test_other_http_errors_keep_status_without_remote_text(monkeypatch):
    from urllib.error import HTTPError
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    def fail(*args, **kwargs):
        raise HTTPError("https://provider", 401, "test-secret", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(DepartmentProviderError, match="HTTP 401") as error:
        build_department_generator(DepartmentProviderConfig(allow_external=True))("work")
    assert "test-secret" not in str(error.value)


@pytest.mark.parametrize("failure, category, status", [
    ("auth", "auth", 403), ("http", "http", 503),
    ("network", "network", None), ("malformed", "malformed", None),
])
def test_provider_structured_diagnostics_do_not_expose_remote_text(monkeypatch, failure, category, status):
    from urllib.error import HTTPError, URLError
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-secret")
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"private-secret":true}'
    def transport(*args, **kwargs):
        if failure in ("auth", "http"):
            raise HTTPError("https://private-secret", status, "private-secret", {}, None)
        if failure == "network":
            raise URLError("private-secret")
        return Response()
    monkeypatch.setattr("urllib.request.urlopen", transport)
    with pytest.raises(DepartmentProviderError) as error:
        build_department_generator(DepartmentProviderConfig(allow_external=True))("work")
    assert error.value.category == category
    assert error.value.http_status == status
    assert "private-secret" not in error.value.safe_diagnostic
