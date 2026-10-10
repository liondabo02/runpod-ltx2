"""Read-only local readiness report; never sends prompts or enables billing."""
import json
import os
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime, timezone


def local_json(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:11434" + path, timeout=5) as response:
        return json.load(response)


def main():
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_no_cloud_requests",
        "gemini": {
            "cli_installed": bool(shutil.which("gemini")),
            "api_key_present": bool(os.environ.get("GEMINI_API_KEY")),
            "authentication_verified": False,
            "free_quota_verified": False,
            "coding_execution_verified": False,
            "consumer_google_login": "retired_2026_06_18_migrate_to_antigravity",
        },
        "antigravity_cli_installed": bool(shutil.which("agy") or (
            Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
        ).is_file()),
        "key_presence_scope": "invoking_process_environment_only",
        "cloud_key_presence": {
            name: bool(os.environ.get(name)) for name in
            ("OPENROUTER_API_KEY", "GROQ_API_KEY", "HF_TOKEN", "NVIDIA_API_KEY", "BYTEZ_API_KEY")
        },
        "automatic_paid_fallback_enabled": False,
    }
    try:
        models = local_json("/api/tags").get("models", [])
        report["local_models"] = [
            {"name": item.get("name"), "size_bytes": item.get("size")}
            for item in models if isinstance(item, dict)
        ]
        loaded = local_json("/api/ps").get("models", [])
        report["loaded_models"] = [
            {"name": item.get("name"), "context_length": item.get("context_length"),
             "gpu_bytes": item.get("size_vram")}
            for item in loaded if isinstance(item, dict)
        ]
        report["ollama_available"] = True
    except (OSError, ValueError):
        report["ollama_available"] = False
        report["local_models"] = []
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
