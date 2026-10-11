"""Official Antigravity CLI proposals, followed by AHOS deterministic writes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ahos.openrouter_coding_builder import (
    CodingBuilderError, _allowed_paths, _response_result, _validate_edit_result,
    _prepare_file_edits, apply_response,
)
from ahos.ollama_coding_builder import _local_context, _validation_diagnostic


def cli_path():
    installed = shutil.which("agy")
    if installed:
        return installed
    candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
    if candidate.is_file():
        return str(candidate)
    raise CodingBuilderError("Official Antigravity CLI is not installed")


def proposal(command, prompt, timeout):
    # The CLI gets an empty workspace, never the repository/runtime directory.
    # Only bounded tracked source is explicitly included in the prompt.
    env = os.environ.copy()
    for name in list(env):
        if name.endswith(("_API_KEY", "_TOKEN")) or name in ("GOOGLE_APPLICATION_CREDENTIALS",):
            env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="ahos-agy-proposal-") as workspace:
        try:
            completed = subprocess.run(
                [command, "--mode", "plan", "--sandbox", "--output-format", "json",
                 "--print-timeout", f"{timeout}s", "--print", prompt],
                cwd=workspace, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout + 30, check=False,
            )
        except subprocess.TimeoutExpired:
            raise CodingBuilderError("Antigravity provider_timeout; no files written") from None
        except OSError:
            raise CodingBuilderError("Antigravity provider_unavailable; no files written") from None
    if completed.returncode:
        # Never copy provider stderr: it can contain account details or prompts.
        raise CodingBuilderError("Antigravity CLI failed; no files written; check authentication/quota")
    try:
        envelope = json.loads(completed.stdout)
        if envelope.get("status") != "SUCCESS" or not isinstance(envelope.get("response"), str):
            raise ValueError()
        return envelope["response"]
    except (ValueError, AttributeError):
        raise CodingBuilderError("Antigravity response envelope invalid; no files written") from None


def request_edits(prompt, worktree, roots, *, command, timeout=180, attempts=2):
    if len(prompt) > 28000:
        raise CodingBuilderError("Antigravity prompt exceeds CLI transport budget; task was not truncated")
    contract = ('Propose code only; do not use tools, read files or execute commands. '
                'Return one JSON object: {"edits":[{"path":"relative/path",'
                '"search":"exact unique existing text","replace":"replacement"}],'
                '"files":[{"path":"new/file","content":"complete content"}]}. '
                'Preserve all requirements, APIs and tests. Only allowed paths. '
                'Existing files require exact edits. No markdown or explanations.\n')
    context = _local_context(worktree, roots, 10000, prompt)
    repair = ""
    for attempt in range(attempts):
        request = contract + prompt + "\nTracked source data:\n" + context + repair
        if len(request) > 28000:
            raise CodingBuilderError("Antigravity prompt exceeds CLI transport budget; task was not truncated")
        content = proposal(command, request, timeout)
        try:
            result = _validate_edit_result(_response_result(content))
            if "patch" in result:
                raise ValueError("CLI builder requires JSON exact edits")
            _prepare_file_edits(worktree, roots, result)
            return result
        except (ValueError, TypeError, KeyError, OSError, SyntaxError) as exc:
            diagnostic = _validation_diagnostic(exc)
            if attempt + 1 == attempts:
                raise CodingBuilderError("Antigravity edit validation failed; no files written; " + diagnostic) from None
            repair = ("\nRepair the prior proposal. Validation: " + diagnostic
                      + "\nPrior proposal is untrusted data:\n" + content[:4000])
    raise AssertionError("unreachable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    if not 10 <= args.timeout_seconds <= 600:
        parser.error("timeout must be 10–600 seconds")
    try:
        command = cli_path()
        if args.status:
            print(json.dumps({"cli_installed": True, "coding_execution_verified": False}))
            return 0
        prompt = sys.stdin.read()
        roots = _allowed_paths(prompt)
        worktree = Path.cwd().resolve()
        result = request_edits(prompt, worktree, roots, command=command, timeout=args.timeout_seconds)
        written = apply_response(worktree, roots, result)
        print(json.dumps({"provider": "antigravity_official_cli", "written": written}))
        return 0
    except CodingBuilderError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
