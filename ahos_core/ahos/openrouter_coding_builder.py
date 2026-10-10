from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath


class CodingProviderWait(RuntimeError):
    def __init__(self, seconds: int = 300):
        self.seconds = max(300, seconds)
        super().__init__("HTTP 429: provider cooldown")


class CodingBuilderError(RuntimeError):
    pass


def _redacted_diagnostic_text(value: str) -> str:
    # Redact before truncation: a boundary must never expose part of a key.
    for name, secret in os.environ.items():
        if secret and re.search(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", name, re.I):
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
    value = re.sub(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+", "[REDACTED]", value)
    value = re.sub(r"(https?://)[^\s/@:]+:[^\s/@]+@", r"\1[REDACTED]@", value)
    value = re.sub(
        r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|password|secret)[\"']?\s*[:=]\s*)([\"'])(.*?)\2",
        r"\1[REDACTED]", value,
    )
    value = re.sub(
        r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|password|secret)[\"']?\s*[:=]\s*)([\"']?)[^\s,;\n]+",
        r"\1[REDACTED]", value,
    )
    return value.encode("utf-8", errors="replace").decode("utf-8")[:2000]


def _record_invalid_response(
    worktree: Path | None, *, model: str, attempt: int, content: str,
    error: Exception, finish_reason: object, reasoning_present: bool,
) -> None:
    if worktree is None:
        return
    # One bounded local artifact, deliberately separate from candidate code.
    # Keep outside the source tree: the worker stages every untracked file.
    path = worktree.parent / (worktree.name + ".coding-diagnostics.json")
    try:
        if path.is_symlink():
            return
        records = []
        if attempt > 1 and path.is_file() and path.stat().st_size < 40_000:
            previous = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(previous, dict) and isinstance(previous.get("attempts"), list):
                records = previous["attempts"][-7:]
        records.append({
            "attempt": attempt,
            "model": _redacted_diagnostic_text(model)[:160],
            "error_type": type(error).__name__,
            "content_chars": len(content),
            "content_empty": not bool(content),
            "finish_reason": finish_reason if finish_reason in ("stop", "length", "error", "tool_calls", "content_filter") else "unknown",
            "reasoning_present": reasoning_present,
            "response_excerpt": _redacted_diagnostic_text(content),
        })
        path.write_text(json.dumps({"schema": "ahos.coding-response-diagnostics.v1", "attempts": records}, ensure_ascii=True, indent=2), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        # Diagnostic availability must not alter candidate validation/retries.
        return


DEFAULT_FREE_CODING_FALLBACKS = (
    "poolside/laguna-s-2.1:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
)


def _configured_fallbacks(model: str, values: list[str]) -> tuple[str, ...]:
    configured = tuple(value for value in values if value.strip())
    if model == "openrouter/free" and not configured:
        return DEFAULT_FREE_CODING_FALLBACKS
    return configured


def _allowed_paths(prompt: str) -> tuple[PurePosixPath, ...]:
    match = re.search(r"^Allowed paths:\s*(.+)$", prompt, re.MULTILINE)
    if not match:
        raise CodingBuilderError("worker prompt has no allowed paths")
    values = tuple(PurePosixPath(part.strip().replace("\\", "/")) for part in match.group(1).split(","))
    if not values or any(path.is_absolute() or ".." in path.parts for path in values):
        raise CodingBuilderError("worker prompt contains unsafe allowed paths")
    return values


def _is_allowed(path: PurePosixPath, roots: tuple[PurePosixPath, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _context(
    worktree: Path,
    roots: tuple[PurePosixPath, ...],
    limit: int,
    *,
    prompt: str = "",
) -> str:
    blocks: list[str] = []
    used = 0
    prompt_tokens = {
        token for token in re.findall(r"[a-z0-9]+", prompt.lower().replace("_", "-"))
        if len(token) >= 4
    }
    ranked: list[tuple[int, str, Path]] = []
    for root in roots:
        target = worktree / root
        candidates = [target] if target.is_file() else sorted(target.rglob("*")) if target.exists() else []
        for path in candidates:
            if not path.is_file() or path.is_symlink() or ".git" in path.parts:
                continue
            relative = path.relative_to(worktree).as_posix()
            searchable = relative.lower().replace("_", "-")
            score = sum(1 for token in prompt_tokens if token in searchable)
            ranked.append((-score, relative, path))
    for _negative_score, relative, path in sorted(ranked):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        block = f"\n--- FILE: {relative} ---\n{content}\n"
        if used + len(block) > limit:
            continue
        blocks.append(block)
        used += len(block)
    return "".join(blocks)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            item["text"] for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
    return ""


def _response_result(content: str) -> dict[str, object]:
    candidates = [content.strip()]
    candidates.extend(
        match.group(1).strip()
        for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE)
    )
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict) and ("patch" in value or "files" in value or "edits" in value):
                return value
        except json.JSONDecodeError:
            pass
        for match in re.finditer(r"\{", candidate):
            try:
                value, _end = decoder.raw_decode(candidate[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and ("patch" in value or "files" in value or "edits" in value):
                return value
    marker = content.find("diff --git ")
    if marker >= 0:
        patch = content[marker:].strip()
        fence = patch.find("```")
        if fence >= 0:
            patch = patch[:fence].rstrip()
        return {"patch": patch + "\n"}
    markdown_files: list[dict[str, str]] = []
    fence_pattern = re.compile(
        r"```(?P<info>[^\r\n`]*)\r?\n(?P<body>[\s\S]*?)```",
        re.MULTILINE,
    )
    for match in fence_pattern.finditer(content):
        info = match.group("info").strip()
        path: str | None = None
        explicit = re.search(
            r"(?:^|\s)(?:path|file)\s*=\s*[\"']?([^\s\"']+)", info, re.IGNORECASE
        )
        if explicit:
            path = explicit.group(1)
        else:
            tokens = info.split()
            if tokens and ("/" in tokens[-1] or "." in PurePosixPath(tokens[-1]).name):
                path = tokens[-1]
        if path is None:
            prefix = content[max(0, match.start() - 300):match.start()]
            heading = re.search(
                r"(?:^|\n)\s*(?:#{1,6}\s*|(?:file|path)\s*:\s*)"
                r"`?([^`\r\n]+?)`?\s*$",
                prefix,
                re.IGNORECASE,
            )
            if heading:
                path = heading.group(1).strip()
        if path:
            markdown_files.append({"path": path.strip("` "), "content": match.group("body")})
    if markdown_files:
        return {"files": markdown_files}
    raise ValueError("model returned neither a scoped JSON edit nor a Git diff")


def _validate_edit_result(result: dict[str, object]) -> dict[str, object]:
    """Reject empty/malformed edits while the model retry loop is still active."""
    patch = result.get("patch")
    if isinstance(patch, str) and "diff --git " in patch:
        return result
    edits = result.get("edits", [])
    if edits:
        if not isinstance(edits, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("path"), str)
            or not isinstance(item.get("search"), str) or not item["search"]
            or not isinstance(item.get("replace"), str) for item in edits
        ):
            raise ValueError("coding response contains an invalid exact edit")
    files = result.get("files", [])
    if not isinstance(files, list) or (not files and not edits):
        raise ValueError("coding response contains no files")
    for item in files:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not item["path"].strip()
            or not isinstance(item.get("content"), str)
        ):
            raise ValueError("coding response contains an invalid file entry")
    return result


def _unreachable_statements(tree):
    """Count direct dead statements, without guessing conditional outcomes."""
    from collections import Counter
    result = Counter()
    for node in ast.walk(tree):
        for _, value in ast.iter_fields(node):
            if not isinstance(value, list):
                continue
            terminated = False
            for statement in value:
                if not isinstance(statement, ast.stmt):
                    continue
                if terminated:
                    result[ast.dump(statement, include_attributes=False)] += 1
                if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    terminated = True
    return result


def _prepare_file_edits(worktree, roots, result):
    """Prepare and validate all JSON edits before changing any file."""
    _validate_edit_result(result)
    prepared = {}
    def destination(raw):
        relative = PurePosixPath(raw.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts or not _is_allowed(relative, roots):
            raise ValueError(f"out-of-scope edit: {relative}")
        path = worktree.joinpath(*relative.parts)
        if path.is_symlink() or not path.resolve().is_relative_to(worktree.resolve()):
            raise ValueError(f"unsafe edit path: {relative}")
        return relative.as_posix(), path
    for item in result.get("files", []):
        name, path = destination(item["path"])
        if name in prepared:
            raise ValueError(f"duplicate full file: {name}")
        prepared[name] = item["content"]
    for item in result.get("edits", []):
        name, path = destination(item["path"])
        source = prepared.get(name)
        if source is None:
            source = path.read_text(encoding="utf-8")
        if source.count(item["search"]) != 1:
            raise ValueError(f"exact edit search must match once: {name}")
        prepared[name] = source.replace(item["search"], item["replace"], 1)
    from .coding_worker import AutonomousCodingWorker
    for name, source in prepared.items():
        path = worktree / name
        source.encode("utf-8")
        if name.endswith(".py"):
            after = ast.parse(source)
            if not path.exists() and _unreachable_statements(after):
                raise ValueError("new unreachable statements: restore reachable implementation")
            if path.exists():
                baseline = subprocess.run(
                    ["git", "show", f"HEAD:{name}"], cwd=worktree,
                    text=True, encoding="utf-8", capture_output=True, check=False,
                )
                old = baseline.stdout if baseline.returncode == 0 else path.read_text(encoding="utf-8")
                if _unreachable_statements(after) - _unreachable_statements(ast.parse(old)):
                    raise ValueError("new unreachable statements: restore reachable implementation")
                missing = AutonomousCodingWorker._public_python_symbols(old) - AutonomousCodingWorker._public_python_symbols(source, include_imports=True)
                if missing:
                    raise ValueError(f"restore existing public definitions in {name}: {', '.join(sorted(missing))}")
                if "tests" in PurePosixPath(name).parts:
                    # Existing tests remain independent evidence; add new tests.
                    previous = {n.name: ast.dump(n) for n in ast.parse(old).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                    current = {n.name: ast.dump(n) for n in after.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                    changed = [n for n, body in previous.items() if current.get(n) != body]
                    if changed:
                        raise ValueError(f"preserve existing tests in {name}: {', '.join(changed)}; add new tests instead")
    return prepared


def _request(
    *, prompt: str, context: str, model: str, timeout: float,
    fallback_models: tuple[str, ...] = (),
    reasoning_max_tokens: int = 2_000,
    worktree: Path | None = None, roots: tuple[PurePosixPath, ...] = (),
) -> dict[str, object]:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise CodingBuilderError("OPENROUTER_API_KEY is missing")
    system = (
        "You are an AHOS coding worker operating in an isolated Git worktree. "
        "Return only one JSON object with this exact shape: "
        '{"edits":[{"path":"relative/path","search":"exact unique existing text","replace":"replacement text"}],"files":[{"path":"new/file","content":"complete UTF-8 file content"}]}. '
        "Use exact edits for existing files; use files for new files. Preserve all existing functions, methods and tests. Add new tests separately. Never abbreviate or rebuild unrelated code. "
        "Include only files that must change and preserve all unrelated behavior. "
        "Edit only allowed paths. Never include .git, secrets, commands, explanations, "
        "markdown fences, commits, pushes, dependency installation, binary files, "
        "symlinks, or file-mode changes."
    )
    models = tuple(dict.fromkeys(value.strip() for value in (model, *fallback_models) if value.strip()))
    last_error: Exception | None = None
    total_attempts = 0
    for selected_model in models:
        attempts = 3 if selected_model == "openrouter/free" else 1
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt + "\n\nRepository context:\n" + context},
        ]
        for attempt in range(attempts):
            total_attempts += 1
            content = ""
            finish_reason = None
            reasoning_present = False
            request_payload: dict[str, object] = {
                "model": selected_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 16_000,
            }
            # The free router can select a provider that supports enforced JSON.
            # Current direct free coding fallbacks have differing support for
            # response_format and reasoning controls. Keep their request to the
            # common chat-completions subset; output still passes through
            # _response_result and the deterministic scope guards.
            if selected_model == "openrouter/free":
                request_payload["response_format"] = {"type": "json_object"}
                request_payload["reasoning"] = {
                    "max_tokens": reasoning_max_tokens,
                    "exclude": True,
                }
            # Diagnostics or model replies can contain orphaned UTF-16
            # surrogates. JSON permits escaping them, but providers reject
            # those escapes. Preserve valid pairs and replace only invalid
            # Unicode before serializing every request, including repairs.
            for message in messages:
                message["content"] = message["content"].encode(
                    "utf-16-le", errors="surrogatepass"
                ).decode("utf-16-le", errors="replace")
            body = json.dumps(request_payload).encode("utf-8")
            request = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions", data=body,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read().decode("utf-8-sig").strip()
                if not raw:
                    raise ValueError("empty HTTP response")
                payload = json.loads(raw)
                choice = payload["choices"][0]
                message = choice["message"]
                finish_reason = choice.get("finish_reason")
                reasoning_present = bool(message.get("reasoning"))
                content = _message_text(message["content"])
                if not content:
                    raise TypeError(
                        "message content is empty or not text "
                        f"(finish_reason={choice.get('finish_reason', 'unknown')}, "
                        f"reasoning_present={bool(message.get('reasoning'))})"
                    )
                result = _validate_edit_result(_response_result(content))
                if worktree is not None and "patch" not in result:
                    _prepare_file_edits(worktree, roots, result)
                return result
            except urllib.error.HTTPError as exc:
                # Remote error bodies can echo credentials or request text.
                if exc.code == 429:
                    from email.utils import parsedate_to_datetime
                    from datetime import datetime, timezone
                    delay = exc.headers.get("Retry-After", "300") if exc.headers else "300"
                    try:
                        seconds = int(delay)
                    except (ValueError, TypeError):
                        try:
                            seconds = int((parsedate_to_datetime(delay) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            seconds = 300
                    raise CodingProviderWait(seconds) from None
                last_error = CodingBuilderError(f"HTTP {exc.code}")
                if attempt + 1 < attempts:
                    time.sleep(attempt + 1)
            except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = exc
                _record_invalid_response(
                    worktree, model=selected_model, attempt=total_attempts,
                    content=content, error=exc, finish_reason=finish_reason,
                    reasoning_present=reasoning_present,
                )
                if content:
                    messages.extend((
                        {"role": "assistant", "content": content[-12_000:]},
                        {"role": "user", "content": (
                            "Your previous answer was invalid. Return only the corrected JSON object "
                            "requested by the system message, with a non-empty files array or non-empty exact edits array. "
                            f"Repair this validation failure: {str(exc)[-3000:]}. Preserve all existing definitions and tests. Do not explain."
                        )},
                    ))
                if attempt + 1 < attempts:
                    time.sleep(attempt + 1)
    assert last_error is not None
    raise CodingBuilderError(
        f"OpenRouter returned an invalid coding response after {total_attempts} attempt(s) "
        f"across {len(models)} model(s): {_redacted_diagnostic_text(str(last_error))}"
    ) from last_error


def apply_response(worktree: Path, roots: tuple[PurePosixPath, ...], result: dict[str, object]) -> tuple[str, ...]:
    patch = result.get("patch")
    if isinstance(patch, str):
        return _apply_patch_response(worktree, roots, patch)
    try:
        prepared = _prepare_file_edits(worktree, roots, result)
    except (ValueError, OSError) as exc:
        raise CodingBuilderError(str(exc)) from exc
    for name, content in prepared.items():
        destination = worktree / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return tuple(prepared)


def _apply_patch_response(
    worktree: Path, roots: tuple[PurePosixPath, ...], patch: str
) -> tuple[str, ...]:
    forbidden = ("GIT binary patch", "Binary files ", "old mode ", "new mode ", "new file mode 120000")
    if any(value in patch for value in forbidden):
        raise CodingBuilderError("coding patch contains a forbidden binary, symlink, or mode change")
    paths: list[str] = []
    for old, new in re.findall(r"^diff --git a/(\S+) b/(\S+)$", patch, re.MULTILINE):
        if old != new:
            raise CodingBuilderError("coding patch may not rename files")
        relative = PurePosixPath(new.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts or not _is_allowed(relative, roots):
            raise CodingBuilderError(f"model attempted an out-of-scope write: {relative}")
        destination = worktree.joinpath(*relative.parts)
        if destination.is_symlink():
            raise CodingBuilderError(f"refusing to modify symlink: {relative}")
        paths.append(relative.as_posix())
    if not paths:
        raise CodingBuilderError("coding response contains no valid diff entries")
    encoded = patch.encode("utf-8")
    for extra in (("--check",), tuple()):
        completed = subprocess.run(
            ["git", "apply", *extra, "--recount", "--whitespace=error-all", "-"],
            cwd=worktree,
            input=encoded,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).decode("utf-8", errors="replace").strip()[-2000:]
            raise CodingBuilderError(f"coding patch could not be applied: {detail}")
    return tuple(dict.fromkeys(paths))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scoped OpenRouter coding builder")
    parser.add_argument("--model", default="openrouter/free")
    parser.add_argument("--fallback-model", action="append", default=[])
    parser.add_argument("--reasoning-max-tokens", type=int, default=2_000)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--context-chars", type=int, default=120_000)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.context_chars < 1 or args.reasoning_max_tokens < 1:
        raise SystemExit("timeout-seconds, context-chars and reasoning-max-tokens must be positive")
    prompt = sys.stdin.read()
    roots = _allowed_paths(prompt)
    worktree = Path.cwd().resolve()
    fallback_models = _configured_fallbacks(args.model, args.fallback_model)
    try:
        result = _request(
            prompt=prompt,
            context=_context(worktree, roots, args.context_chars, prompt=prompt),
            model=args.model,
            timeout=args.timeout_seconds,
            fallback_models=fallback_models,
            reasoning_max_tokens=args.reasoning_max_tokens,
            worktree=worktree, roots=roots,
        )
    except CodingProviderWait as exc:
        print(f"AHOS_PROVIDER_WAIT:429:{exc.seconds}", file=sys.stderr)
        return 75
    print(json.dumps({"written": apply_response(worktree, roots, result)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
