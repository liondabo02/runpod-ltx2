"""Best-effort bridge to the holding's growth engine (ahos_core.agent_growth).

Studio workers call guidance(worker_id) to receive the allow-listed coaching text
that the evidence-based growth engine produced for them. It is advisory only:
it can never unlock capabilities, spending or owner approvals.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("AHOS_RUNTIME_DIR", str(ROOT / "runtime")))


def guidance(worker_id):
    record = {"worker_id": worker_id, "source": "unavailable",
              "available": False, "guidance": ""}
    try:
        core = str(ROOT / "ahos_core")
        if core not in sys.path:
            sys.path.insert(0, core)
        from ahos.agent_growth import prompt_guidance  # type: ignore
        text = prompt_guidance(RUNTIME, worker_id) or ""
        record.update({"source": "ahos_core.agent_growth", "available": True,
                       "guidance": text[:2000]})
    except Exception as exc:  # growth engine is optional at runtime
        record["error"] = str(exc)[:200]
    return record


def numeric_hint(record, key, default):
    """Read 'key=value' from the coaching text; never trust other formats."""
    for token in (record.get("guidance") or "").split():
        if token.startswith(key + "="):
            try:
                return float(token.split("=", 1)[1])
            except ValueError:
                return default
    return default
