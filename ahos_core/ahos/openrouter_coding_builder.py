from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


def _request(*, prompt: str, context: str, model: str, timeout: float) -> dict[str, object]:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise CodingBuilderError("OPENROUTER_API_KEY is missing")
    system = (
        "You are an AHOS coding worker operating in an isolated Git worktree. "
        "Return strict JSON only: {\"files\":[{\"path\":\"relative/path\","
        "\"content\":\"complete replacement text\"}]}. Edit only allowed paths. "
        "Never include .git, secrets, commands, explanations, markdown, commits, pushes, "
        "dependency installation, or partial snippets. Keep changes minimal and tested."
    )
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt + "\n\nRepository context:\n" + context},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = json.loads(payload["choices"][0]["message"]["content"])
    except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise CodingBuilderError(f"OpenRouter returned an invalid coding response: {exc}") from exc
    if not isinstance(result, dict):
        raise CodingBuilderError("coding response must be a JSON object")
    return result


def apply_response(worktree: Path, roots: tuple[PurePosixPath, ...], result: dict[str, object]) -> tuple[str, ...]:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Scoped OpenRouter coding builder")
    parser.add_argument("--model", default="openrouter/free")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--context-chars", type=int, default=120_000)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.context_chars < 1:
        raise SystemExit("timeout-seconds and context-chars must be positive")
    prompt = sys.stdin.read()
    roots = _allowed_paths(prompt)
    worktree = Path.cwd().resolve()
    result = _request(prompt=prompt, context=_context(worktree, roots, args.context_chars), model=args.model, timeout=args.timeout_seconds)
    print(json.dumps({"written": apply_response(worktree, roots, result)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
