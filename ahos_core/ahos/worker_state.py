"""V5 GÖREV 013 — İşçi durum makinesi (working/learning/...).

Durum yalnız gözlenen kayıtlardan türetilir; öğrenme durumu üretim sayılmaz.
Kayıt: `runtime/worker-states.json` (yeniden başlatmaya dayanıklı).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

STATES = ("working", "researching", "learning", "reviewing", "collaborating",
          "waiting_dependency", "waiting_approval", "blocked", "idle", "offline")


def _path(runtime) -> Path:
    return Path(runtime) / "worker-states.json"


def _load(runtime) -> dict:
    try:
        data = json.loads(_path(runtime).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def set_state(runtime, worker: str, state: str, *, note: str = "") -> dict:
    if state not in STATES:
        raise ValueError(f"invalid worker state: {state}")
    data = _load(runtime)
    record = {"worker": str(worker), "state": state, "note": str(note)[:200],
              "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    data[str(worker)] = record
    path = _path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def get_state(runtime, worker: str) -> dict:
    return _load(runtime).get(str(worker)) or {"worker": str(worker), "state": "offline",
                                               "note": "kayıt yok", "updated_at": ""}


def derive_from_event(runtime, worker: str, *, event: str, ok: bool = True,
                      note: str = "") -> dict:
    """Gözlenen olaydan durum türetir; bilinmeyen olay offline sayılır."""

    mapping = {"mission": "working", "research": "researching",
               "learning": "learning", "review": "reviewing",
               "collaboration": "collaborating", "dependency": "waiting_dependency",
               "approval": "waiting_approval", "blocked": "blocked", "idle": "idle"}
    state = mapping.get(str(event), "idle")
    if not ok and state == "working":
        state = "blocked"
    return set_state(runtime, worker, state, note=note or event)


def all_states(runtime) -> list[dict]:
    return sorted(_load(runtime).values(), key=lambda row: row.get("worker", ""))
