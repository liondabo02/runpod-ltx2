"""G011 — İşçiler arası gerçek yardımlaşma ve bağımsız QA.

Yardım yalnız mesaj değildir: talep → çözüm önerisi → bağımsız doğrulayıcı →
QA kanıtı → ortak bilgiye aktarma. Kendi önerisini veya kendi talebini doğrulayan
işçi kabul edilmez. Başarısız çözüm ortak bilgiye yazılmaz.

Kayıt: `runtime/cognition/_help.jsonl` (append-only; durum son olaydan türetilir).
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from . import cognitive_memory as cm

OPEN = "open"
PROPOSED = "proposed"
VERIFIED = "verified"
REJECTED = "rejected"


def _path(runtime) -> Path:
    directory = Path(runtime) / "cognition"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "_help.jsonl"


def _append(runtime, record: dict) -> dict:
    with _path(runtime).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _events(runtime, request_id: str | None = None) -> list[dict]:
    path = _path(runtime)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if request_id is None or row.get("request_id") == request_id:
            rows.append(row)
    return rows


def open_request(runtime, *, mission_id: str, from_worker: str, skill: str,
                 evidence: str = "") -> dict:
    request_id = f"help-{int(time.time())}-{secrets.token_hex(3)}"
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "request_id": request_id,
              "event": OPEN, "mission_id": str(mission_id), "from": str(from_worker),
              "skill": str(skill), "evidence": str(evidence)[:300]}
    return _append(runtime, record)


def propose(runtime, request_id: str, *, helper: str, solution: str,
            expected_result: str = "", evidence: str = "") -> dict:
    state = status(runtime, request_id)
    if state is None:
        raise KeyError(request_id)
    if state["state"] != OPEN:
        raise RuntimeError(f"request is {state['state']}, not open")
    if str(helper) == state["from"]:
        raise PermissionError("requester cannot propose a solution to themselves")
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "request_id": request_id,
              "event": PROPOSED, "helper": str(helper), "solution": str(solution)[:600],
              "expected_result": str(expected_result)[:300], "evidence": str(evidence)[:300]}
    return _append(runtime, record)


def verify(runtime, request_id: str, *, verifier: str, ok: bool,
           note: str = "", evidence_ok: bool = False) -> dict:
    """Bağımsız doğrulama; pass yalnız QA kanıtı varsa ortak bilgiye yazılır."""

    state = status(runtime, request_id)
    if state is None:
        raise KeyError(request_id)
    if state["state"] != PROPOSED:
        raise RuntimeError(f"request is {state['state']}, not proposed")
    verifier = str(verifier)
    if verifier in {state["from"], state.get("helper")}:
        raise PermissionError("independent verifier required (requester/helper cannot verify)")
    if ok and not evidence_ok:
        raise ValueError("verified help requires independent QA evidence")
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "request_id": request_id,
              "event": VERIFIED if ok else REJECTED, "verifier": verifier,
              "ok": bool(ok), "note": str(note)[:300], "evidence_ok": bool(evidence_ok)}
    _append(runtime, record)
    if ok:
        cm.share_knowledge(
            runtime, department=str(state.get("department") or ""),
            statement=(f"yardım çözümü: {state.get('skill')} — "
                       f"{state.get('solution', '')[:200]}"),
            source=f"help:{request_id}", mission_id=str(state.get("mission_id") or ""),
            verified=True)
    return record


def status(runtime, request_id: str) -> dict | None:
    rows = _events(runtime, request_id)
    if not rows:
        return None
    state = {"request_id": request_id, "state": OPEN, "events": len(rows)}
    for row in rows:
        event = row.get("event")
        if event in {OPEN, PROPOSED, VERIFIED, REJECTED}:
            state["state"] = event
        for key in ("mission_id", "from", "skill", "helper", "solution",
                    "expected_result", "verifier", "ok", "note", "evidence_ok",
                    "department"):
            if key in row:
                state[key] = row[key]
    return state


def stats(runtime) -> dict:
    rows = _events(runtime)
    requests = {row["request_id"] for row in rows if row.get("request_id")}
    verified = {row["request_id"] for row in rows if row.get("event") == VERIFIED}
    rejected = {row["request_id"] for row in rows if row.get("event") == REJECTED}
    return {"requests": len(requests), "verified": len(verified),
            "rejected": len(rejected), "open": len(requests - verified - rejected)}
