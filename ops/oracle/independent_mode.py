"""Opt-in reversible AHOS free-first cloud mode. Never calls paid providers.

On-demand cloud inference already occurs only when a bounded AHOS model task
runs. This tool safely switches the daemon's NEXT loadable model config.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

MODEL = "qwen2.5-coder:3b"
API = "http://127.0.0.1:11500"
MANAGED = {
    "AHOS_EXECUTOR": "model",
    "AHOS_ALLOW_PAID_LLM": "0",
    "AHOS_LLM_BASE_URL": API + "/v1",
    "AHOS_LLM_API_KEY": "local-only",
    "AHOS_LLM_MODEL": MODEL,
    "AHOS_LLM_MODELS": MODEL,
    "AHOS_LLM_MAX_USD": "0",
    "AHOS_LLM_FREE": "1",
    "AHOS_DAILY_USD": "0",
    "AHOS_LLM_TIMEOUT": "180",
    "AHOS_LLM_MAX_TOKENS": "512",
}
REMOVED = {
    "AHOS_FALLBACK_BASE_URL", "AHOS_FALLBACK_API_KEY",
    "AHOS_FALLBACK_MODEL", "AHOS_FALLBACK_TIMEOUT",
}


def cloud_ready(*, request=urlopen) -> bool:
    try:
        with request(API + "/api/tags", timeout=5) as response:
            if response.status != 200:
                return False
            data = json.load(response)
        return any(row.get("name") == MODEL for row in data.get("models", []) if isinstance(row, dict))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def transform(original: str) -> str:
    """Retain unrelated keys including safety approvals, remove paid credentials.

    The verbatim original is backed up outside Git first, with no disclosure.
    """
    preserved: list[str] = []
    for line in original.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in MANAGED or key in REMOVED:
                continue
        preserved.append(line)
    while preserved and not preserved[-1].strip():
        preserved.pop()
    preserved += [f"{key}={value}" for key, value in MANAGED.items()]
    return "\n".join(preserved) + "\n"


def atomic_write(path: Path, content: bytes) -> None:
    descriptor, temp_path = tempfile.mkstemp(prefix=".ahos-mode-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        # Windows'ta hedef dosya kisa sure baska bir tutamak (antivirus,
        # OneDrive, okuma) tarafindan kilitli olabiliyor: sinirli yeniden dene.
        last_error: OSError | None = None
        for attempt in range(6):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError as exc:  # hedef gecici olarak kilitli
                last_error = exc
                time.sleep(0.05 * (attempt + 1))
        raise last_error if last_error is not None else RuntimeError("atomic_write failed")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def switch(env_path: Path, *, probe=cloud_ready) -> dict[str, str]:
    """Switch NEXT daemon launch only. Active Python processes are unchanged."""
    if not probe():
        raise RuntimeError("Oracle 3B model not confirmed; active mode unchanged")
    current = env_path.read_bytes()
    target = transform(current.decode("utf-8-sig")).encode("utf-8")
    if current == target:
        return {"result": "already_independent", "restart_required": "true"}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = Path.home() / ".ahos-private" / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"model.env.before-owned-cloud-{stamp}.bak"
    with backup.open("xb") as handle:
        handle.write(current)
        handle.flush()
        os.fsync(handle.fileno())
    # Avoid overwriting another agent's last-second update.
    if env_path.read_bytes() != current:
        backup.unlink(missing_ok=True)
        raise RuntimeError("Another agent changed model.env; not overwriting")
    atomic_write(env_path, target)
    return {"result": "switched_next_launch", "backup": str(backup), "restart_required": "true"}


def restore(env_path: Path, backup: Path) -> dict[str, str]:
    """Restore only a backup created by this tool and only from owned-cloud mode."""
    approved_dir = (Path.home() / ".ahos-private" / "backups").resolve()
    if backup.resolve().parent != approved_dir or not backup.name.startswith("model.env.before-owned-cloud-"):
        raise ValueError("Unrecognized independent-mode backup path")
    if not env_path.is_file():
        raise FileNotFoundError("Current model.env not found")
    current = env_path.read_text(encoding="utf-8-sig")
    if "AHOS_LLM_BASE_URL=" + API + "/v1" not in current:
        raise RuntimeError("Live model config has changed; refuse automatic rollback")
    atomic_write(env_path, backup.read_bytes())
    return {"result": "original_config_restored", "restart_required": "true"}


def describe(env_path: Path, *, probe=cloud_ready) -> dict[str, object]:
    text = env_path.read_text(encoding="utf-8-sig") if env_path.exists() else ""
    vals = dict(line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("#"))
    return {
        "oracle_3b_responding": probe(),
        "owned_cloud_primary": vals.get("AHOS_LLM_BASE_URL") == API + "/v1",
        "model": vals.get("AHOS_LLM_MODEL", ""),
        "paid_disabled": vals.get("AHOS_ALLOW_PAID_LLM") == "0",
        "token_cost_ceiling_zero": vals.get("AHOS_LLM_MAX_USD") == "0",
        "env_present": env_path.exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--apply", action="store_true")
    operation.add_argument("--restore", type=Path)
    args = parser.parse_args()
    try:
        if args.apply:
            result = switch(args.env)
            print(json.dumps(result, ensure_ascii=False))
        elif args.restore:
            result = restore(args.env, args.restore)
            print(json.dumps(result, ensure_ascii=False))
        print(json.dumps(describe(args.env), ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
