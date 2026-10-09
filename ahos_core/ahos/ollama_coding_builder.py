"""Local Ollama builder; delegates writes to the existing scoped edit validator."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

# Also support an absolute script entrypoint from an isolated candidate checkout.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ahos.openrouter_coding_builder import (
    CodingBuilderError, _allowed_paths, _context, _message_text,
    _prepare_file_edits, _response_result, _validate_edit_result, apply_response,
)

ENDPOINT = "http://127.0.0.1:11434"


def _validation_diagnostic(exc: Exception) -> str:
    """Report the failed gate without logging model text or repository contents."""
    if isinstance(exc, SyntaxError):
        return "python_syntax: generated Python is invalid"
    if isinstance(exc, FileNotFoundError):
        return "missing_file: an exact edit targets a file that does not exist"
    if isinstance(exc, OSError):
        return "file_io: could not read or prepare an edit"
    message = str(exc)
    gates = {
        "out-of-scope edit:": "scope: generated path is outside allowed paths",
        "unsafe edit path:": "unsafe_path: generated path is unsafe",
        "duplicate full file:": "duplicate_file: response repeats a full file",
        "exact edit search must match once:": "exact_search: search text is missing or is not unique",
        "restore existing public definitions": "public_definitions: response removes existing definitions",
        "preserve existing tests": "existing_tests: response changes or removes existing tests",
        "Ollama generation incomplete": "truncated: generation is incomplete or reached its output limit",
    }
    for prefix, diagnostic in gates.items():
        if message.startswith(prefix):
            return diagnostic
    return "response_format: response does not satisfy the JSON edit contract"


def _post(path: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        ENDPOINT + path, data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    # Ignore machine-wide proxies; never redirect repository text off loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Ollama response must be an object")
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise CodingBuilderError("Ollama redirects are disabled")


def request_edits(prompt: str, worktree: Path, roots: tuple[PurePosixPath, ...],
                  *, model: str, timeout: float, context_chars: int, attempts: int) -> dict:
    messages = [
        {"role": "system", "content": (
            'Return only JSON: {"edits":[{"path":"relative/path","search":"exact unique existing text",'
            '"replace":"replacement"}],"files":[{"path":"new/file","content":"complete content"}]}. '
            "Use edits for existing files and files for new files. Preserve existing functions and tests. "
            "Change only allowed paths. No commands, secrets, commits, pushes or dependency installation."
        )},
        {"role": "user", "content": prompt + "\nRepository context:\n" +
         _context(worktree, roots, context_chars, prompt=prompt)},
    ]
    for attempt in range(attempts):
        try:
            payload = _post("/api/chat", {
                "model": model, "messages": messages, "stream": False, "format": "json",
                "keep_alive": "5m",
                "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 4096},
            }, timeout)
        except (OSError, ValueError, urllib.error.URLError):
            raise CodingBuilderError("Local Ollama request failed; check service and downloaded model") from None
        content = _message_text(payload.get("message", {}).get("content")) if isinstance(payload.get("message"), dict) else ""
        try:
            if payload.get("done") is not True or payload.get("done_reason") == "length":
                raise ValueError("Ollama generation incomplete or truncated")
            result = _validate_edit_result(_response_result(content))
            if "patch" in result:
                raise ValueError("local builder requires JSON exact edits")
            _prepare_file_edits(worktree, roots, result)
            return result
        except (ValueError, TypeError, KeyError, OSError, SyntaxError) as exc:
            diagnostic = _validation_diagnostic(exc)
            if attempt + 1 == attempts:
                raise CodingBuilderError(
                    "Local model failed scoped edit validation; no files written; " + diagnostic
                ) from None
            messages.extend([
                {"role": "assistant", "content": content[-6000:]},
                {"role": "user", "content": "Repair the JSON edits; preserve all tests and functions. Validation: " + diagnostic},
            ])
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Check model availability without generating or downloading")
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--context-chars", type=int, default=16000)
    parser.add_argument("--attempts", type=int, default=2)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.context_chars < 1 or not 1 <= args.attempts <= 3:
        parser.error("positive timeout/context and 1–3 attempts required")
    if args.model != "qwen2.5-coder:7b":
        parser.error("this local adapter currently supports only qwen2.5-coder:7b")
    if args.status:
        try:
            metadata = _post("/api/show", {"model": args.model}, min(args.timeout_seconds, 10))
            available = isinstance(metadata.get("details"), dict) and not metadata.get("error")
        except (OSError, ValueError, CodingBuilderError):
            available = False
        print(json.dumps({"provider": "ollama_local", "endpoint": ENDPOINT,
                          "model": args.model, "model_available": available,
                          "coding_execution_verified": False}))
        return 0 if available else 1
    prompt = sys.stdin.read()
    worktree = Path.cwd().resolve()
    try:
        roots = _allowed_paths(prompt)
        result = request_edits(prompt, worktree, roots, model=args.model,
                               timeout=args.timeout_seconds, context_chars=args.context_chars,
                               attempts=args.attempts)
        written = apply_response(worktree, roots, result)
    except CodingBuilderError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"provider": "ollama_local", "written": written}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
