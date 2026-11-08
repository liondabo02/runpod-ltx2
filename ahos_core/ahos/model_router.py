"""Task-aware model selection with credential-aware fallback.

The route changes *only* the model name for the already configured endpoint.
No URL, API key, paid permission, or model download is fabricated here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

_CONFIG = Path(__file__).resolve().parents[1] / "config" / "models.json"


def pick(kind: str, *, settings=None, env: Mapping[str, str] | None = None,
         config_path: str | Path | None = None) -> str:
    """Return a model compatible with the active endpoint or its existing fallback.

    A remote candidate requires an API key in the supplied environment. A route
    never switches hosts. Missing/invalid configuration leaves settings.model
    untouched, rather than silently sending a task to another provider.
    """
    source = os.environ if env is None else env
    fallback = str(getattr(settings, "model", "") or source.get("AHOS_LLM_MODEL") or "").strip()
    endpoint = str(getattr(settings, "base_url", "") or source.get("AHOS_LLM_BASE_URL") or "").strip().rstrip("/").lower()
    if not endpoint:
        return fallback
    try:
        config = json.loads(Path(config_path or _CONFIG).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return fallback
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        return fallback
    routes = config.get("routes")
    if not isinstance(routes, dict):
        return fallback
    name = "deterministic" if kind == "deterministic" else "complex"
    candidates = routes.get(name)
    if not isinstance(candidates, list):
        return fallback
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        model = entry.get("model")
        expected = str(entry.get("base_url_prefix") or "").rstrip("/").lower()
        if not isinstance(model, str) or not model.strip() or not expected:
            continue
        if endpoint != expected and not endpoint.startswith(expected + "/"):
            continue
        key_name = entry.get("api_key_env")
        if key_name:
            if not isinstance(key_name, str):
                continue
            key = str(source.get(key_name) or source.get("AHOS_LLM_API_KEY") or "").strip()
            if not key or key == "local-only":
                continue
        else:
            # No-key entries are only safe for an actual loopback endpoint.
            if not (endpoint.startswith("http://127.0.0.1:") or endpoint.startswith("http://localhost:")):
                continue
        return model.strip()
    return fallback
