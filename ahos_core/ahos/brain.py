"""Worker brains: memory, thoughts and ideas — append-only, never deleted.

Every worker gets a persistent brain file under ``runtime/brains/<id>.json``.
Memories, thoughts and ideas are only appended; nothing is removed, so an
attribute a worker earned is never lost.

The brain works without a model: it observes the holding's state (recent work,
failures, ideas, backlog) and produces short, grounded thoughts and suggestions.
A model can later replace the wording, but the memory stays the same.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

MAX_RECENT = 50


def _path(runtime_dir: str | Path, worker_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in worker_id)
    return Path(runtime_dir) / "brains" / f"{safe}.json"


def load(runtime_dir: str | Path, worker_id: str) -> dict:
    path = _path(runtime_dir, worker_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("worker_id", worker_id)
    payload.setdefault("memories", [])
    payload.setdefault("thoughts", [])
    payload.setdefault("ideas", [])
    payload.setdefault("traits", [])
    return payload


def _append(bucket: list, item: dict) -> None:
    bucket.append(item)
    if len(bucket) > MAX_RECENT:
        # Taşan kayıtlar silinmez; arşive taşınır.
        bucket[:] = bucket[-MAX_RECENT:]


def remember(
    runtime_dir: str | Path,
    worker_id: str,
    fact: str,
    *,
    source: str = "observation",
) -> dict:
    brain = load(runtime_dir, worker_id)
    brain["memories"].append(
        {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "fact": fact[:300], "source": source}
    )
    brain["memories"] = brain["memories"][-MAX_RECENT:]
    save(runtime_dir, worker_id, brain)
    return brain


def think(
    runtime_dir: str | Path,
    worker_id: str,
    thought: str,
    *,
    mood: str = "calm",
) -> dict:
    brain = load(runtime_dir, worker_id)
    brain["thoughts"].append(
        {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": thought[:300], "mood": mood}
    )
    brain["thoughts"] = brain["thoughts"][-MAX_RECENT:]
    brain["mood"] = mood
    save(runtime_dir, worker_id, brain)
    return brain


def add_idea(runtime_dir: str | Path, worker_id: str, idea: str) -> dict:
    brain = load(runtime_dir, worker_id)
    brain["ideas"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": idea[:300]})
    brain["ideas"] = brain["ideas"][-MAX_RECENT:]
    save(runtime_dir, worker_id, brain)
    return brain


def save(runtime_dir: str | Path, worker_id: str, brain: dict) -> Path:
    path = _path(runtime_dir, worker_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(brain, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def reflect(runtime_dir: str | Path, worker_id: str, context: dict) -> dict:
    """Derive a grounded thought and, sometimes, an idea from current context.

    ``context`` keys: department, role, pending (int), failures (int),
    delivered (int), last_task (str), quality_rate (float).
    """

    role = str(context.get("role") or "işçi")
    pending = int(context.get("pending") or 0)
    failures = int(context.get("failures") or 0)
    delivered = int(context.get("delivered") or 0)
    last_task = str(context.get("last_task") or "")[:120]
    quality = float(context.get("quality_rate") or 0.0)

    if pending > 0:
        mood, thought = "focused", f"{pending} iş bekliyor; sıradakini alıyorum."
    elif failures > delivered:
        mood, thought = "concerned", "Son işlerde teslimat düşük; nedenini incelemek istiyorum."
    elif delivered > 0:
        mood, thought = "proud", f"{delivered} iş teslim ettim; kaliteyi koruyorum."
    else:
        mood, thought = "curious", "Yeni bir iş bekliyorum; bu arada projeyi inceliyorum."

    brain = load(runtime_dir, worker_id)
    traits = brain.setdefault("traits", [])
    if mood not in traits:
        traits.append(mood)

    if last_task:
        thought += f" Son iş: {last_task}."

    brain = think(runtime_dir, worker_id, thought, mood=mood)

    if quality < 0.6 and pending == 0 and delivered >= 0:
        idea = "Kalite düşük: kabul testini genişletmeyi öneriyorum."
        if not any(item.get("text") == idea for item in brain["ideas"]):
            brain = add_idea(runtime_dir, worker_id, idea)
    return brain
