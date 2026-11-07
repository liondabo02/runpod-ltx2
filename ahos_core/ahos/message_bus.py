"""V5 GÖREV 007 — İşçiler arası güvenli, kayıtlı, tekrarsız mesajlaşma.

- 11 mesaj tipi; görev dışı sohbet reddedilir.
- Aynı (gönderen, alıcı, görev, tip, içerik) TTL içinde tekrar edilirse yeni kayıt açılmaz.
- Görev başına mesaj tavanı ve çift başına tur tavanı (sonsuz döngü engeli).
- Kayıt append-only JSONL; ack kalıcıdır, yeniden başlatmada korunur.
- Yetki/harcama değiştirmez; mesaj yalnız koordinasyon verisidir.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

MESSAGE_TYPES = ("task_request", "help_request", "research_result", "knowledge_share",
                 "review_request", "review_result", "handoff", "blocker", "decision",
                 "completion", "escalation")
DEDUPE_TTL_SECONDS = 600
MISSION_CAP = 120
PAIR_CAP = 10


def _path(runtime) -> Path:
    directory = Path(runtime) / "messages"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "messages.jsonl"


def _rows(runtime) -> list[dict]:
    path = _path(runtime)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _payload_hash(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        .encode("utf-8")).hexdigest()[:16]


def _moment(row: dict) -> float:
    try:
        return time.mktime(time.strptime(str(row.get("timestamp"))[:19],
                                         "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return 0.0


def send(runtime, *, from_worker: str, to_worker: str, mission_id: str,
         message_type: str, payload: dict | None = None, correlation_id: str = "",
         priority: str = "normal") -> dict:
    if message_type not in MESSAGE_TYPES:
        raise ValueError(f"unknown message type: {message_type}")
    if not from_worker or not to_worker or from_worker == to_worker:
        raise ValueError("from/to must be distinct workers")
    if not mission_id:
        raise ValueError("mission_id is required")
    payload = payload or {}
    digest = _payload_hash(payload)
    now = time.time()
    rows = _rows(runtime)
    for row in reversed(rows):
        if (row.get("event") == "message" and now - _moment(row) <= DEDUPE_TTL_SECONDS
                and row.get("from_worker") == from_worker
                and row.get("to_worker") == to_worker
                and row.get("mission_id") == mission_id
                and row.get("message_type") == message_type
                and row.get("payload_hash") == digest):
            return {**row, "duplicate": True}

    mission_rows = [r for r in rows if r.get("event") == "message"
                    and r.get("mission_id") == mission_id]
    if len(mission_rows) >= MISSION_CAP:
        raise RuntimeError(f"mission message cap reached: {MISSION_CAP}")
    pair = [r for r in mission_rows if r.get("from_worker") == from_worker
            and r.get("to_worker") == to_worker]
    if len(pair) >= PAIR_CAP:
        raise RuntimeError(f"pair message cap reached: {PAIR_CAP}")

    record = {"event": "message", "message_id": f"msg-{uuid.uuid4().hex[:12]}",
              "from_worker": str(from_worker), "to_worker": str(to_worker),
              "mission_id": str(mission_id), "message_type": message_type,
              "payload": payload, "payload_hash": digest,
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "correlation_id": str(correlation_id), "priority": str(priority),
              "status": "pending"}
    with _path(runtime).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def ack(runtime, message_id: str, *, worker: str) -> dict:
    row = next((item for item in reversed(_rows(runtime))
                if item.get("message_id") == message_id), None)
    if row is None or row.get("event") != "message":
        raise KeyError(message_id)
    if row.get("to_worker") != worker:
        raise PermissionError("only the recipient can acknowledge")
    record = {"event": "ack", "message_id": message_id, "worker": worker,
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with _path(runtime).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def state(runtime) -> dict[str, dict]:
    """message_id → {message..., acked bool} (yeniden başlatmaya dayanıklı)."""

    state_map: dict[str, dict] = {}
    for row in _rows(runtime):
        if row.get("event") == "message":
            state_map[row["message_id"]] = {**row, "acked": False}
        elif row.get("event") == "ack" and row.get("message_id") in state_map:
            state_map[row["message_id"]]["acked"] = True
    return state_map


def inbox(runtime, worker: str, *, limit: int = 50) -> list[dict]:
    return [row for row in state(runtime).values()
            if row.get("to_worker") == worker and not row.get("acked")][:limit]


def stats(runtime) -> dict:
    rows = state(runtime).values()
    return {"messages": len(rows),
            "pending": sum(1 for row in rows if not row.get("acked")),
            "acked": sum(1 for row in rows if row.get("acked")),
            "types": sorted({row.get("message_type") for row in rows})}
