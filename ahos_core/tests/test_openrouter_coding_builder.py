import json
from pathlib import Path, PurePosixPath

import pytest

from ahos.openrouter_coding_builder import (
    CodingBuilderError, DEFAULT_FREE_CODING_FALLBACKS, _allowed_paths,
    _configured_fallbacks, _context, _request, _response_result, _validate_edit_result,
    apply_response,
)


def test_free_router_retries_transient_invalid_content(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(("not a patch", "diff --git a/src/app.py b/src/app.py\n"))

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = next(responses)
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    calls = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: calls.append(1) or Response())
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    result = _request(prompt="task", context="ctx", model="openrouter/free", timeout=1)

    assert result == {"patch": "diff --git a/src/app.py b/src/app.py\n"}
    assert len(calls) == 2


def test_retry_tells_model_to_repair_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(("not a patch", "diff --git a/src/app.py b/src/app.py\n"))
    bodies = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": next(responses)}}]}).encode()

    def urlopen(request, **_kwargs):
        bodies.append(json.loads(request.data))
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    _request(prompt="task", context="ctx", model="openrouter/free", timeout=1)

    assert bodies[1]["messages"][-2]["content"] == "not a patch"
    assert "previous answer was invalid" in bodies[1]["messages"][-1]["content"]
    assert bodies[1]["reasoning"] == {"max_tokens": 2_000, "exclude": True}
    assert bodies[1]["response_format"] == {"type": "json_object"}


def test_empty_files_response_is_repaired_inside_model_retry_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter((
        '{"files": []}',
        '{"files": [{"path": "src/app.py", "content": "VALUE = 2\\n"}]}',
    ))
    bodies = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": next(responses)}}]
            }).encode()

    def urlopen(request, **_kwargs):
        bodies.append(json.loads(request.data))
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    result = _request(
        prompt="task", context="ctx", model="openrouter/free", timeout=1
    )

    assert result["files"][0]["path"] == "src/app.py"
    assert len(bodies) == 2
    assert "non-empty files array" in bodies[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    "result",
    (
        {"files": []},
        {"files": [{}]},
        {"files": [{"path": "", "content": "x"}]},
        {"patch": ""},
    ),
)
def test_edit_validation_rejects_unusable_results(result) -> None:
    with pytest.raises(ValueError):
        _validate_edit_result(result)


def test_reasoning_budget_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": "diff --git a/src/app.py b/src/app.py\n"},
                }]
            }).encode()

    def urlopen(request, **_kwargs):
        bodies.append(json.loads(request.data))
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    _request(
        prompt="task", context="ctx", model="openrouter/free", timeout=1,
        reasoning_max_tokens=1_000,
    )

    assert bodies[0]["reasoning"] == {"max_tokens": 1_000, "exclude": True}


def test_falls_back_to_next_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    models = []

    class Response:
        def __init__(self, content):
            self.content = content

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": self.content}}]}).encode()

    def urlopen(request, **_kwargs):
        model = json.loads(request.data)["model"]
        models.append(model)
        content = "invalid" if model == "primary/model" else "diff --git a/src/app.py b/src/app.py\n"
        return Response(content)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    result = _request(
        prompt="task", context="ctx", model="primary/model", timeout=1,
        fallback_models=("fallback/model",),
    )

    assert models == ["primary/model", "fallback/model"]
    assert result["patch"].startswith("diff --git")


def test_direct_free_fallback_omits_unsupported_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {
                    "content": "diff --git a/src/app.py b/src/app.py\n"
                }}]
            }).encode()

    def urlopen(request, **_kwargs):
        bodies.append(json.loads(request.data))
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    _request(
        prompt="task", context="ctx", model=DEFAULT_FREE_CODING_FALLBACKS[0],
        timeout=1,
    )

    assert "response_format" not in bodies[0]
    assert "reasoning" not in bodies[0]


def test_free_router_gets_resilient_default_fallbacks() -> None:
    assert _configured_fallbacks("openrouter/free", []) == DEFAULT_FREE_CODING_FALLBACKS
    assert _configured_fallbacks("primary/model", []) == ()
    assert _configured_fallbacks("openrouter/free", ["owner/model"]) == ("owner/model",)


def test_repository_context_prioritizes_files_named_by_the_task(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a_large_unrelated.py").write_text("X = '" + "x" * 500 + "'\n")
    (source / "control_center.py").write_text("class ControlCenterState:\n    pass\n")

    context = _context(
        tmp_path,
        (PurePosixPath("src"),),
        150,
        prompt="Add System Health to the Control Center dashboard",
    )

    assert "FILE: src/control_center.py" in context
    assert "ControlCenterState" in context
    assert "a_large_unrelated.py" not in context


def test_extracts_json_edit_from_markdown_fence_and_surrounding_text() -> None:
    result = _response_result(
        'Here is the edit:\n```json\n{"files": [{"path": "src/app.py", "content": "ok\\n"}]}\n```'
    )
    assert result["files"] == [{"path": "src/app.py", "content": "ok\n"}]


def test_extracts_diff_without_trailing_markdown_fence() -> None:
    result = _response_result(
        "```diff\ndiff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n```"
    )
    assert result["patch"].endswith("+++ b/src/app.py\n")


def test_extracts_markdown_file_blocks_with_explicit_paths() -> None:
    result = _response_result(
        "### `src/app.py`\n```python\nVALUE = 2\n```\n"
        "```text path=tests/test_app.py\ndef test_value():\n    assert True\n```"
    )
    assert result["files"] == [
        {"path": "src/app.py", "content": "VALUE = 2\n"},
        {"path": "tests/test_app.py", "content": "def test_value():\n    assert True\n"},
    ]


def test_markdown_file_block_still_obeys_scope_guard(tmp_path: Path) -> None:
    result = _response_result("```python path=../escape.py\nbad = True\n```")
    with pytest.raises(CodingBuilderError, match="out-of-scope"):
        apply_response(tmp_path, (PurePosixPath("src"),), result)


def test_allowed_paths_are_read_from_supervisor_prompt() -> None:
    assert _allowed_paths("Allowed paths: src, tests/unit\n") == (
        PurePosixPath("src"), PurePosixPath("tests/unit")
    )


def test_response_writes_only_scoped_files(tmp_path: Path) -> None:
    written = apply_response(tmp_path, (PurePosixPath("src"),), {
        "files": [{"path": "src/app.py", "content": "VALUE = 2\n"}]
    })
    assert written == ("src/app.py",)
    assert (tmp_path / "src" / "app.py").read_text() == "VALUE = 2\n"


def test_compact_diff_response_applies_only_scoped_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "app.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    written = apply_response(tmp_path, (PurePosixPath("src"),), {
        "patch": """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-VALUE = 1
+VALUE = 2
"""
    })
    assert written == ("src/app.py",)
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"


def test_diff_response_rejects_out_of_scope_file(tmp_path: Path) -> None:
    with pytest.raises(CodingBuilderError, match="out-of-scope"):
        apply_response(tmp_path, (PurePosixPath("src"),), {
            "patch": """diff --git a/docs/escape.md b/docs/escape.md
--- a/docs/escape.md
+++ b/docs/escape.md
@@ -0,0 +1 @@
+bad
"""
        })


@pytest.mark.parametrize("path", ["../secret", ".git/config", "docs/escape.md", "/absolute"])
def test_response_rejects_out_of_scope_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(CodingBuilderError, match="out-of-scope"):
        apply_response(tmp_path, (PurePosixPath("src"),), {
            "files": [{"path": path, "content": "bad"}]
        })


def test_requests_normalize_orphan_surrogates_and_preserve_unicode(monkeypatch):
    bodies = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {
                "content": "diff --git a/src/app.py b/src/app.py\n"
            }}]}).encode()

    def urlopen(request, **_kwargs):
        payload = json.loads(request.data)
        content = payload["messages"][1]["content"]
        content.encode("utf-8", errors="strict")
        bodies.append(content)
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    _request(prompt="Türkçe \ud83d\ude00 \ud83d", context="Kurmancî \udc00",
             model="openrouter/free", timeout=1)
    assert "Türkçe 😀 �" in bodies[0]
    assert "Kurmancî �" in bodies[0]


def test_exact_edits_preserve_unrelated_functions(tmp_path):
    source = "def keep():\n    return 1\n\ndef change():\n    return 2\n"
    (tmp_path / "app.py").write_text(source)
    result = _response_result(json.dumps({"edits": [{"path": "app.py", "search": "    return 2", "replace": "    return 3"}]}))
    assert apply_response(tmp_path, (PurePosixPath("app.py"),), result) == ("app.py",)
    assert (tmp_path / "app.py").read_text() == source.replace("return 2", "return 3")


def test_exact_edits_validate_whole_batch_before_writes(tmp_path):
    (tmp_path / "app.py").write_text("VALUE = 1\n")
    with pytest.raises(CodingBuilderError, match="match once"):
        apply_response(tmp_path, (PurePosixPath("app.py"),), {"edits": [
            {"path": "app.py", "search": "VALUE = 1", "replace": "VALUE = 2"},
            {"path": "app.py", "search": "missing", "replace": "bad"},
        ]})
    assert (tmp_path / "app.py").read_text() == "VALUE = 1\n"


def test_existing_tests_cannot_be_rewritten_by_json_edits(tmp_path):
    (tmp_path / "tests").mkdir()
    path = tmp_path / "tests/test_app.py"
    old = "def test_existing():\n    assert 1 == 1\n"
    path.write_text(old)
    with pytest.raises(CodingBuilderError, match="preserve existing tests"):
        apply_response(tmp_path, (PurePosixPath("tests"),), {"files": [{
            "path": "tests/test_app.py", "content": old.replace("assert 1 == 1", "pass")
        }]})
    assert path.read_text() == old
    apply_response(tmp_path, (PurePosixPath("tests"),), {"files": [{
        "path": "tests/test_app.py", "content": old + "\ndef test_new():\n    assert True\n"
    }]})


def test_removed_definitions_are_repaired_before_write(monkeypatch, tmp_path):
    path = tmp_path / "app.py"
    old = "def existing():\n    return 1\n"
    path.write_text(old)
    responses = iter([{"files": [{"path": "app.py", "content": "VALUE = 2\n"}]},
                      {"edits": [{"path": "app.py", "search": "return 1", "replace": "return 2"}]}])
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self):
            return json.dumps({"choices": [{"message": {"content": json.dumps(next(responses))}}]}).encode()
    def urlopen(request, **_kwargs):
        requests.append(json.loads(request.data))
        assert path.read_text() == old
        return Response()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda _: None)
    result = _request(prompt="task", context=old, model="openrouter/free", timeout=1,
                      worktree=tmp_path, roots=(PurePosixPath("app.py"),))
    assert "restore existing public definitions" in requests[1]["messages"][-1]["content"]
    apply_response(tmp_path, (PurePosixPath("app.py"),), result)
    assert path.read_text() == old.replace("return 1", "return 2")


def test_invalid_response_diagnostics_are_bounded_and_redacted(tmp_path, monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"finish_reason": "length", "message": {
                "content": "Bearer test-key sk-unknownsecret api_key=other-secret " + "x" * 5000,
                "reasoning": "private reasoning never persisted",
            }}]}).encode()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: Response())
    monkeypatch.setattr("time.sleep", lambda _s: None)
    with pytest.raises(CodingBuilderError):
        _request(prompt="private prompt", context="private repository context", model="openrouter/free",
                 timeout=1, worktree=tmp_path)
    artifact = tmp_path.parent / (tmp_path.name + ".coding-diagnostics.json")
    assert list(tmp_path.iterdir()) == []  # Never enter the candidate Git diff.
    text = artifact.read_text()
    for secret in ("test-key", "sk-unknownsecret", "other-secret", "private prompt", "private repository context", "private reasoning"):
        assert secret not in text
    records = json.loads(text)["attempts"]
    assert len(records) == 3
    assert records[-1]["finish_reason"] == "length"
    assert records[-1]["reasoning_present"] is True
    assert len(records[-1]["response_excerpt"]) <= 2000
    assert records[-1]["content_chars"] > 5000


def test_empty_response_diagnostic_has_no_reasoning_content(tmp_path, monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self):
            return json.dumps({"choices": [{"finish_reason": "stop", "message": {
                "content": "", "reasoning": "do not persist this",
            }}]}).encode()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: Response())
    with pytest.raises(CodingBuilderError):
        _request(prompt="task", context="ctx", model="direct/free", timeout=1, worktree=tmp_path)
    record = json.loads((tmp_path.parent / (tmp_path.name + ".coding-diagnostics.json")).read_text())["attempts"][0]
    assert record["content_empty"] is True
    assert record["response_excerpt"] == ""
    assert record["reasoning_present"] is True


def test_429_stops_fallbacks_and_preserves_retry_after(monkeypatch):
    import urllib.error
    from ahos.openrouter_coding_builder import CodingProviderWait
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-secret')
    calls = []
    def limited(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError('https://example.test', 429, 'limited', {'Retry-After': '900'}, None)
    monkeypatch.setattr('urllib.request.urlopen', limited)
    with pytest.raises(CodingProviderWait) as caught:
        _request(prompt='task', context='', model='openrouter/free', timeout=1,
                 fallback_models=('qwen/test:free',))
    assert caught.value.seconds == 900
    assert len(calls) == 1
