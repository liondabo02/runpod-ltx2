from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath


class CodingBuilderError(RuntimeError):
    pass


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


def _context(worktree: Path, roots: tuple[PurePosixPath, ...], limit: int) -> str:
    blocks: list[str] = []
    used = 0
    for root in roots:
        target = worktree / root
        candidates = [target] if target.is_file() else sorted(target.rglob("*")) if target.exists() else []
        for path in candidates:
            if not path.is_file() or path.is_symlink() or ".git" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            relative = path.relative_to(worktree).as_posix()
            block = f"\n--- FILE: {relative} ---\n{content}\n"
            if used + len(block) > limit:
                return "".join(blocks)
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
            if isinstance(value, dict) and ("patch" in value or "files" in value):
                return value
        except json.JSONDecodeError:
            pass
        for match in re.finditer(r"\{", candidate):
            try:
                value, _end = decoder.raw_decode(candidate[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and ("patch" in value or "files" in value):
                return value
    marker = content.find("diff --git ")
    if marker >= 0:
        patch = content[marker:].strip()
        fence = patch.find("```")
        if fence >= 0:
            patch = patch[:fence].rstrip()
        return {"patch": patch + "\n"}
    raise ValueError("model returned neither a scoped JSON edit nor a Git diff")


def _request(
    *, prompt: str, context: str, model: str, timeout: float,
    fallback_models: tuple[str, ...] = (),
) -> dict[str, object]:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise CodingBuilderError("OPENROUTER_API_KEY is missing")
    system = (
        "You are an AHOS coding worker operating in an isolated Git worktree. "
        "Return only a standard unified Git diff beginning with 'diff --git'. "
        "Include the smallest complete patch needed for the task; do not return entire "
        "unchanged files. Edit only allowed paths. Never include .git, secrets, commands, "
        "explanations, markdown fences, commits, pushes, dependency installation, binary "
        "files, symlinks, or file-mode changes."
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
            body = json.dumps({
                "model": selected_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 16_000,
            }).encode("utf-8")
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
                content = _message_text(payload["choices"][0]["message"]["content"])
                if not content:
                    raise TypeError("message content is empty or not text")
                return _response_result(content)
            except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = exc
                if content:
                    messages.extend((
                        {"role": "assistant", "content": content[-12_000:]},
                        {"role": "user", "content": (
                            "Your previous answer was invalid. Return only the corrected scoped JSON edit "
                            "or unified Git diff requested by the system message. Do not explain."
                        )},
                    ))
                if attempt + 1 < attempts:
                    time.sleep(attempt + 1)
    assert last_error is not None
    raise CodingBuilderError(
        f"OpenRouter returned an invalid coding response after {total_attempts} attempt(s) "
        f"across {len(models)} model(s): {last_error}"
    ) from last_error


def apply_response(worktree: Path, roots: tuple[PurePosixPath, ...], result: dict[str, object]) -> tuple[str, ...]:
    patch = result.get("patch")
    if isinstance(patch, str):
        return _apply_patch_response(worktree, roots, patch)
    files = result.get("files")
    if not isinstance(files, list) or not files:
        raise CodingBuilderError("coding response contains no files")
    written: list[str] = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
            raise CodingBuilderError("coding response contains an invalid file entry")
        relative = PurePosixPath(item["path"].replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts or not _is_allowed(relative, roots):
            raise CodingBuilderError(f"model attempted an out-of-scope write: {relative}")
        destination = worktree.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise CodingBuilderError(f"refusing to replace symlink: {relative}")
        destination.write_text(item["content"], encoding="utf-8")
        written.append(relative.as_posix())
    return tuple(written)


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
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--context-chars", type=int, default=120_000)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.context_chars < 1:
        raise SystemExit("timeout-seconds and context-chars must be positive")
    prompt = sys.stdin.read()
    roots = _allowed_paths(prompt)
    worktree = Path.cwd().resolve()
    result = _request(
        prompt=prompt,
        context=_context(worktree, roots, args.context_chars),
        model=args.model,
        timeout=args.timeout_seconds,
        fallback_models=tuple(args.fallback_model),
    )
    print(json.dumps({"written": apply_response(worktree, roots, result)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
