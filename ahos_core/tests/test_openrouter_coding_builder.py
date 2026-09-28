import json
from pathlib import Path, PurePosixPath

import pytest

from ahos.openrouter_coding_builder import CodingBuilderError, _allowed_paths, _request, apply_response


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
