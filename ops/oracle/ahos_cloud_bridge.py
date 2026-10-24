"""Read-only, zero-paid-call status and safe staging for AHOS Oracle Ollama.

No SSH key contents, paid requests, daemon restarts or authentication changes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PREFERRED_MODELS = ("qwen2.5-coder:7b", "deepseek-r1:7b")
HOST = "127.0.0.1"
PORT = 11500


def ollama_tags(host: str = HOST, port: int = PORT, *, timeout: float = 2.0) -> tuple[str, ...]:
    """Probe ONLY a loopback Ollama tunnel, never an unauthenticated public URL."""
    if host != HOST or not (1 <= int(port) <= 65535):
        raise ValueError("Only 127.0.0.1 endpoints are allowed")
    try:
        with urlopen(f"http://{host}:{port}/api/tags", timeout=timeout) as response:
            if response.status != 200:
                return ()
            payload = json.load(response)
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        return ()
    return tuple(
        m["name"] for m in payload["models"]
        if isinstance(m, dict) and isinstance(m.get("name"), str)
    )


def status(repo: Path, *, probe=ollama_tags) -> dict[str, object]:
    meta_file = repo / "ops" / "oracle" / "last-instance.json"
    metadata = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else {}
    names = probe()
    root = Path.home()
    current_env = repo / "ahos_core" / "runtime" / "model.env"
    # Never disclose values, URLs or token-bearing env fields.
    return {
        "vm_recorded": bool(metadata.get("instance_id")),
        "region": str(metadata.get("region") or ""),
        "shape": str(metadata.get("shape") or ""),
        "tunnel_ready": bool(names),
        "installed_models": list(names),
        "qwen_ready": any(n == "qwen2.5-coder:7b" or n.startswith("qwen2.5-coder:7b-") for n in names),
        "deepseek_distill_ready": any(n == "deepseek-r1:7b" or n.startswith("deepseek-r1:7b-") for n in names),
        "codex_cli_detected": bool(shutil.which("codex") or (root / "AppData/Roaming/npm/codex.cmd").exists()),
        "deepseek_harness_data_detected": (root / ".dsh" / "llm-deepseek").is_dir(),
        "active_configuration_preserved": current_env.is_file(),
    }


def stage(repo: Path, model: str = PREFERRED_MODELS[0], *, probe=ollama_tags) -> Path:
    """Stage a prospective zero-token-charge remote model configuration.

    Does not replace the running model.env or claim a VM is actually free-tier.
    """
    if model not in PREFERRED_MODELS:
        raise ValueError("Model must be one of the supported inspected profiles")
    if model not in probe():
        raise RuntimeError(f"Refusing to stage: {model} not verified through the loopback tunnel")
    target = repo / "ahos_core" / "runtime" / "model.cloud.env"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Existing staged config must not be overwritten: {target}")
    values = {
        "AHOS_EXECUTOR": "model",
        "AHOS_LLM_BASE_URL": f"http://{HOST}:{PORT}/v1",
        "AHOS_LLM_API_KEY": "local-only",
        "AHOS_LLM_MODEL": model,
        "AHOS_LLM_FREE": "1",
        "AHOS_LLM_MAX_USD": "0",
        "AHOS_LLM_MAX_TOKENS": "2048",
    }
    # Exclusive create: no racing agent silently replaces an existing config.
    with target.open("x", encoding="utf-8") as out:
        out.write("".join(f"{key}={value}\n" for key, value in values.items()))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe, zero-cost AHOS Oracle model bridge inspection")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--stage", action="store_true", help="stage ONLY after model/tag verification")
    parser.add_argument("--model", choices=PREFERRED_MODELS, default=PREFERRED_MODELS[0])
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    snapshot = status(repo)
    if args.stage:
        try:
            target = stage(repo, args.model)
            snapshot["staged_path"] = str(target)
        except (OSError, RuntimeError, ValueError) as exc:
            snapshot["stage_error"] = str(exc)
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return 1 if (args.stage and "stage_error" in snapshot) else 0


if __name__ == "__main__":
    raise SystemExit(main())
