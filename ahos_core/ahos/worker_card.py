"""V5 GÖREV 019 — İşçi kartı: gerçek kayıtlardan özgeçmiş/performans görünümü.

Özel hafıza metinleri varsayılan olarak gizlenir; yalnız sayılar ve sonuçlar
gösterilir. Kart hiçbir veriyi değiştirmez.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from . import cognitive_memory as cm
from . import worker_state


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _roster(runtime: Path) -> dict:
    payload = _json(runtime / "departments.json", {"departments": []})
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    for department in departments or []:
        for worker in department.get("workers") or []:
            if worker.get("worker_id"):
                yield {**worker, "department": department.get("department_id")}


def _artifacts(runtime: Path, worker: str) -> list[dict]:
    candidates = [runtime.parents[1] / "deliverables",
                  runtime.parent / "deliverables", runtime / "deliverables"]
    root = next((path for path in candidates if path.is_dir()), candidates[0])
    rows = []
    for manifest in root.glob("*/manifest.json"):
        payload = _json(manifest, {})
        for contributor in payload.get("contributors") or []:
            if contributor.get("worker") == worker:
                rows.append({"delivery_id": payload.get("delivery_id"),
                             "task": contributor.get("task"),
                             "status": contributor.get("status")})
    return rows[-5:]


def exists(runtime, worker: str) -> bool:
    """Kart ancak gerçek bir roster/işçi kaydı varsa açılır (uydurma kart yok)."""

    runtime = Path(runtime)
    if any(row["worker_id"] == worker for row in _roster(runtime)):
        return True
    return any((runtime / folder / f"{worker}.json").is_file()
               for folder in ("minds", "cognition"))


def card(runtime, worker: str, *, include_private: bool = False) -> dict:
    runtime = Path(runtime)
    roster = next((row for row in _roster(runtime) if row["worker_id"] == worker), {})
    profile = cm.load(runtime, worker, str(roster.get("department") or ""))
    mind = _json(runtime / "minds" / f"{worker}.json", {})
    memory = profile.get("memory") or {}
    emotional = profile.get("emotion") or {}
    errors = memory.get("error_memory") or []
    collab = memory.get("collaboration_memory") or []
    try:
        from .agent_office import worker_stats

        last_run = str((worker_stats(runtime).get(worker) or {}).get("last") or "")
    except Exception:  # noqa: BLE001 - metrik dosyası kartı engellemez
        last_run = ""
    state = worker_state.derive(runtime, worker, last_active=last_run)
    result = {
        "worker_id": worker,
        "name": roster.get("name") or worker,
        "role": roster.get("role"),
        "department": roster.get("department"),
        "state": {"code": state["state"], "label": state["label"],
                  "reason": state["reason"], "source": state["source"],
                  "stale": state["stale"], "unknown": state["unknown"]},
        "last_run": last_run,
        "capabilities": list(roster.get("capabilities") or [])[:6],
        "current_task": (memory.get("working") or {}).get("objective"),
        "verified_successes": len((profile.get("evidence") or {})
                                  .get("verified_missions") or []),
        "learned_methods": len(memory.get("procedural") or []),
        "semantic_facts": len(memory.get("semantic") or []),
        "collaboration_count": len(collab),
        "last_collaboration": collab[-1]["helper"] if collab else None,
        "last_error": errors[-1]["cause"] if errors else None,
        "last_qa": (profile.get("meta_memory", {}).get("mission_qa") or {}).get(
            "reliability"),
        "emotion": {key: round(float(value), 2) for key, value in emotional.items()
                    if isinstance(value, (int, float))},
        "last_active": max((str(event.get("at") or "") for event in
                            mind.get("events") or []), default=""),
        "artifacts": _artifacts(runtime, worker),
        "private_memory_hidden": not include_private,
    }
    if include_private:
        result["private"] = {"episodic": memory.get("episodic") or [],
                             "semantic": memory.get("semantic") or [],
                             "errors": errors, "collaboration": collab}
    return result


def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


_CSS = """
:root{color-scheme:dark}body{margin:0;background:#08131f;color:#e6eef8;
font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;padding:24px}
a{color:#63b3ff}h1{font-size:22px;margin:0 0 4px}h2{font-size:14px;margin:22px 0 8px;
text-transform:uppercase;letter-spacing:.08em;color:#8fb2d4}
.badge{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;
background:#12314c;border:1px solid #1e4a70}.warn{background:#4a2c12;border-color:#7a4a1e}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
.box{background:#0d1d2c;border:1px solid #173049;border-radius:10px;padding:12px}
.box small{display:block;color:#8fb2d4;font-size:11px;text-transform:uppercase;
letter-spacing:.05em}.box b{font-size:16px}table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid #173049;vertical-align:top}
th{color:#8fb2d4;font-weight:600;font-size:12px}code{color:#9fd6a8}
"""


def render_html(record: dict) -> str:
    """Salt okunur işçi kartı sayfası. Özel hafıza metni asla gömülmez."""

    state = record.get("state") or {}
    badge = "badge warn" if state.get("stale") or state.get("unknown") else "badge"
    metrics = [("Kanıtlı başarı", record.get("verified_successes")),
               ("Öğrenilen yöntem", record.get("learned_methods")),
               ("Semantik bilgi", record.get("semantic_facts")),
               ("İş birliği", record.get("collaboration_count")),
               ("Son QA güvenilirliği", record.get("last_qa")),
               ("Son görülme", (record.get("last_active") or "—")[:19])]
    boxes = "".join(
        f'<div class="box"><small>{_esc(label)}</small><b>{_esc(value if value is not None else "—")}</b></div>'
        for label, value in metrics)
    emotion = ", ".join(f"{_esc(key)} {_esc(value)}"
                        for key, value in (record.get("emotion") or {}).items()) or "—"
    artifacts = "".join(
        f"<tr><td>{_esc(item.get('delivery_id'))}</td><td>{_esc(item.get('task'))}</td>"
        f"<td>{_esc(item.get('status'))}</td></tr>"
        for item in record.get("artifacts") or []) or (
        "<tr><td colspan=3>kayıtlı teslimat yok</td></tr>")
    return (
        f"<!doctype html><html lang=tr><head><meta charset=utf-8>"
        f"<title>AHOS · {_esc(record.get('name'))}</title><style>{_CSS}</style></head><body>"
        f'<a href="/intelligence">← Intelligence panosu</a>'
        f"<h1>{_esc(record.get('name'))}</h1>"
        f"<div>{_esc(record.get('worker_id'))} · {_esc(record.get('department'))} · "
        f"{_esc(record.get('role'))} · <span class='{badge}'>{_esc(state.get('label'))}</span></div>"
        f"<div><small>Gerekçe: {_esc(state.get('reason'))} · kaynak: {_esc(state.get('source'))}</small></div>"
        f"<h2>Performans</h2><div class=grid>{boxes}</div>"
        f"<h2>Duygu boyutları</h2><div>{emotion}</div>"
        f"<h2>Son hata / düzeltme</h2><div>{_esc(record.get('last_error') or '—')}</div>"
        f"<h2>Teslimatlar</h2><table><tr><th>Teslimat</th><th>Görev</th><th>Durum</th></tr>"
        f"{artifacts}</table>"
        f"<h2>Gizlilik</h2><div><small>Özel hafıza metinleri varsayılan gizlidir; "
        f"yalnız sayılar ve sonuçlar gösterilir.</small></div>"
        "</body></html>"
    )
