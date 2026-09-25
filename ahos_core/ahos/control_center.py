from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .autonomous_company import PersistentMissionQueue, QueueStatus
from .coding_supervisor import CodingSupervisorStore
from .owner_approval import ApprovalStatus, OwnerApprovalInbox
from .virtual_workforce import default_virtual_workforce


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ControlCenterState:
    runtime_dir: Path
    service_launcher: Path | None = None

    def __post_init__(self) -> None:
        self.runtime_dir = Path(self.runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self.service_launcher is not None:
            self.service_launcher = Path(self.service_launcher)

    @property
    def queue_db(self) -> Path:
        return self.runtime_dir / "company-service.db"

    @property
    def approvals_db(self) -> Path:
        return self.runtime_dir / "owner-approvals.db"

    @property
    def heartbeat_path(self) -> Path:
        return self.runtime_dir / "company-service-heartbeat.json"

    @property
    def coding_queue_path(self) -> Path:
        return self.runtime_dir / "coding-supervisor-queue.json"

    @property
    def stop_path(self) -> Path:
        return self.runtime_dir / "company-service.stop"

    @property
    def dashboard_pid_path(self) -> Path:
        return self.runtime_dir / "control-center.pid"

    @property
    def backup_root(self) -> Path:
        return self.runtime_dir / "backups"

    def _heartbeat(self) -> dict[str, object]:
        if not self.heartbeat_path.exists():
            return {"state": "unknown", "timestamp": None, "pid": None}
        try:
            raw = json.loads(self.heartbeat_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"state": "error", "timestamp": None, "pid": None}

        state = str(raw.get("state") or "unknown")
        if self.stop_path.exists():
            state = "stop_requested"

        return {
            "state": state,
            "timestamp": raw.get("timestamp"),
            "pid": raw.get("pid"),
            "mission_id": raw.get("mission_id"),
            "mission_status": raw.get("mission_status"),
        }

    def _worker_last_activity(self, missions) -> dict[str, dict[str, object]]:
        latest: dict[str, dict[str, object]] = {}
        for mission in missions:
            if not mission.result_json:
                continue
            try:
                payload = json.loads(mission.result_json)
            except json.JSONDecodeError:
                continue
            for step in payload.get("steps", []):
                worker_id = step.get("worker_id")
                if not worker_id:
                    continue
                latest[str(worker_id)] = {
                    "task_id": step.get("step_id"),
                    "stage": step.get("stage"),
                    "mission_id": mission.mission_id,
                    "updated_at": mission.updated_at,
                }
        return latest

    def snapshot(self) -> dict[str, object]:
        queue = PersistentMissionQueue(self.queue_db)
        missions = queue.list()
        counts = Counter(m.status.value for m in missions)

        inbox = OwnerApprovalInbox(self.approvals_db)
        approvals = inbox.list()
        waiting = [
            item for item in approvals
            if item.status is ApprovalStatus.WAITING_OWNER_APPROVAL
        ]

        last_activity = self._worker_last_activity(missions)
        coding = CodingSupervisorStore(self.coding_queue_path).status()
        workers = []
        for profile in default_virtual_workforce():
            activity = last_activity.get(profile.worker_id, {})
            workers.append(
                {
                    "worker_id": profile.worker_id,
                    "name": profile.name,
                    "department": profile.department,
                    "role": profile.role.value,
                    "status": "configured",
                    "last_mission": activity.get("mission_id"),
                    "last_task": activity.get("task_id"),
                    "last_stage": activity.get("stage"),
                    "last_activity_at": activity.get("updated_at"),
                    "daily_budget_usd": profile.daily_budget_usd,
                    "paid_ai": profile.can_use_paid_ai,
                }
            )

        return {
            "generated_at": _utc_now(),
            "heartbeat": self._heartbeat(),
            "mission_counts": dict(sorted(counts.items())),
            "missions": [
                {
                    "mission_id": m.mission_id,
                    "department": m.primary_department,
                    "status": m.status.value,
                    "attempts": m.attempts,
                    "max_attempts": m.max_attempts,
                    "updated_at": m.updated_at,
                    "last_error": m.last_error,
                    "objective": m.objective,
                }
                for m in reversed(missions[-50:])
            ],
            "approvals": [
                {
                    "request_id": a.request_id,
                    "mission_id": a.mission_id,
                    "step_id": a.step_id,
                    "title": a.title,
                    "estimated_cost_usd": a.estimated_cost_usd,
                    "status": a.status.value,
                    "created_at": a.created_at,
                }
                for a in reversed(approvals[-50:])
            ],
            "waiting_approval_count": len(waiting),
            "worker_count": len(workers),
            "workers": workers,
            "kill_switch_active": self.stop_path.exists(),
            "coding_supervisor": coding,
        }

    def approve(self, request_id: str) -> str:
        inbox = OwnerApprovalInbox(self.approvals_db)
        req = inbox.approve(request_id)

        still_waiting = [
            item for item in inbox.list_waiting()
            if item.mission_id == req.mission_id
        ]
        if not still_waiting:
            queue = PersistentMissionQueue(self.queue_db)
            mission = queue.get(req.mission_id)
            if mission and mission.status is QueueStatus.WAITING_OWNER_APPROVAL:
                queue.resume_after_owner_approval(req.mission_id)
                return f"approved {request_id}; mission resumed"
        return f"approved {request_id}"

    def reject(self, request_id: str) -> str:
        inbox = OwnerApprovalInbox(self.approvals_db)
        req = inbox.reject(request_id)

        queue = PersistentMissionQueue(self.queue_db)
        mission = queue.get(req.mission_id)
        if mission and mission.status is QueueStatus.WAITING_OWNER_APPROVAL:
            with sqlite3.connect(self.queue_db) as conn:
                conn.execute(
                    """
                    UPDATE missions
                    SET status=?, updated_at=?, last_error=?,
                        lease_owner=NULL, lease_until=NULL
                    WHERE mission_id=? AND status=?
                    """,
                    (
                        QueueStatus.BLOCKED.value,
                        _utc_now(),
                        f"owner rejected approval request {request_id}",
                        req.mission_id,
                        QueueStatus.WAITING_OWNER_APPROVAL.value,
                    ),
                )
            return f"rejected {request_id}; mission blocked"
        return f"rejected {request_id}"

    def activate_kill_switch(self) -> str:
        self.stop_path.write_text(
            f"owner kill switch at {_utc_now()}",
            encoding="utf-8",
        )
        return "kill switch activated"

    def start_company_service(self) -> str:
        self.stop_path.unlink(missing_ok=True)
        if self.service_launcher is None or not self.service_launcher.exists():
            return "stop flag cleared; launcher not configured"

        if os.name == "nt":
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-WindowStyle", "Hidden",
                    "-ExecutionPolicy", "Bypass",
                    "-File", str(self.service_launcher),
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            subprocess.Popen([str(self.service_launcher)])
        return "company service start requested"

    def create_backup(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.backup_root / stamp
        destination.mkdir(parents=True, exist_ok=False)

        copied = 0
        for source in self.runtime_dir.iterdir():
            if not source.is_file():
                continue
            if source.suffix.lower() not in {".db", ".json", ".jsonl"}:
                continue
            shutil.copy2(source, destination / source.name)
            copied += 1

        (destination / "manifest.json").write_text(
            json.dumps(
                {"created_at": _utc_now(), "file_count": copied},
                indent=2,
            ),
            encoding="utf-8",
        )
        return f"backup created: {destination.name} ({copied} files)"


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _badge(status: str) -> str:
    css = "ok"
    if status in {"failed", "blocked", "error", "stop_requested", "rejected"}:
        css = "bad"
    elif status in {"pending", "running", "waiting_owner_approval", "approved"}:
        css = "warn"
    return f'<span class="badge {css}">{_esc(status)}</span>'


def render_dashboard(snapshot: dict[str, object], message: str = "") -> str:
    hb = snapshot["heartbeat"]
    counts = snapshot["mission_counts"]
    coding = snapshot.get("coding_supervisor", {"counts": {}, "tasks": []})
    coding_counts = coding.get("counts", {})

    cards = "".join(
        f'<div class="card"><div class="label">{_esc(k)}</div><div class="value">{_esc(v)}</div></div>'
        for k, v in (
            ("Service", hb.get("state", "unknown")),
            ("Workers", snapshot["worker_count"]),
            ("Running", counts.get("running", 0)),
            ("Queued", counts.get("pending", 0)),
            ("Waiting Approval", snapshot["waiting_approval_count"]),
            ("Blocked / Failed", counts.get("blocked", 0) + counts.get("failed", 0)),
            ("Coding Queue", coding_counts.get("queued", 0)),
            ("Code Approval", coding_counts.get("waiting_owner_approval", 0)),
        )
    )

    approval_rows = []
    for a in snapshot["approvals"]:
        actions = "-"
        if a["status"] == "waiting_owner_approval":
            rid = _esc(a["request_id"])
            actions = (
                '<form class="inline" method="post" action="/action/approve">'
                f'<input type="hidden" name="request_id" value="{rid}">'
                '<button class="approve">Approve</button></form>'
                '<form class="inline" method="post" action="/action/reject">'
                f'<input type="hidden" name="request_id" value="{rid}">'
                '<button class="reject">Reject</button></form>'
            )
        approval_rows.append(
            f'<tr><td>{_esc(a["request_id"])}</td><td>{_esc(a["mission_id"])}</td>'
            f'<td>{_badge(a["status"])}</td><td>${float(a["estimated_cost_usd"]):.4f}</td>'
            f'<td>{actions}</td></tr>'
        )
    approval_html = "".join(approval_rows) or '<tr><td colspan="5">No approval requests.</td></tr>'

    mission_html = "".join(
        f'<tr><td>{_esc(m["mission_id"])}</td><td>{_esc(m["department"])}</td>'
        f'<td>{_badge(m["status"])}</td><td>{_esc(str(m["attempts"]) + "/" + str(m["max_attempts"]))}</td>'
        f'<td class="wide">{_esc(m["last_error"] or m["objective"][:140])}</td></tr>'
        for m in snapshot["missions"]
    ) or '<tr><td colspan="5">No missions yet.</td></tr>'

    worker_html = "".join(
        f'<tr><td>{_esc(w["worker_id"])}</td><td>{_esc(w["department"])}</td>'
        f'<td>{_esc(w["role"])}</td><td>{_badge(w["status"])}</td>'
        f'<td>{_esc(w["last_mission"] or "-")}</td><td>{_esc(w["last_stage"] or "-")}</td>'
        f'<td>{"ON" if w["paid_ai"] else "OFF"}</td></tr>'
        for w in snapshot["workers"]
    )

    coding_html = "".join(
        f'<tr><td>{_esc(t["task_id"])}</td><td>{_badge(t["status"])}</td>'
        f'<td>{_esc(str(t["attempts"]) + "/" + str(t["max_attempts"]))}</td>'
        f'<td class="wide">{_esc(t["last_error"] or t["patch_file"] or t["title"])}</td></tr>'
        for t in coding.get("tasks", [])
    ) or '<tr><td colspan="4">No coding tasks yet.</td></tr>'

    notice = f'<div class="notice">{_esc(message)}</div>' if message else ""

    return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="5">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS Holding Control Center</title>
<style>
:root{{--bg:#0b1020;--panel:#141b2d;--line:#26324b;--text:#e9eefc;--muted:#9cabca;--ok:#33d17a;--warn:#f6c85f;--bad:#ff6b6b;--accent:#7aa2ff}}
*{{box-sizing:border-box}} body{{margin:0;font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text)}}
header{{padding:24px 28px 10px;display:flex;justify-content:space-between;align-items:end}} h1{{margin:0;font-size:26px}}
.sub{{color:var(--muted);font-size:13px;margin-top:6px}} main{{padding:18px 28px 40px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}}
.card,.section{{background:var(--panel);border:1px solid var(--line);border-radius:12px}} .card{{padding:16px}}
.label{{color:var(--muted);font-size:12px;text-transform:uppercase}} .value{{font-size:22px;margin-top:7px;font-weight:650}}
.section{{margin-top:22px;overflow:hidden}} .section h2{{font-size:16px;margin:0;padding:15px 16px;border-bottom:1px solid var(--line)}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--muted)}} .wide{{max-width:520px;color:var(--muted)}} .badge{{display:inline-block;padding:3px 7px;border-radius:999px;background:#20304a;font-size:11px}}
.badge.ok{{color:var(--ok)}} .badge.warn{{color:var(--warn)}} .badge.bad{{color:var(--bad)}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;padding:14px}} button{{border:0;border-radius:8px;padding:9px 12px;font-weight:650;cursor:pointer}}
.approve{{background:var(--ok)}} .reject,.kill{{background:var(--bad)}} .neutral{{background:var(--accent)}} .inline{{display:inline;margin-right:4px}}
.notice{{margin-bottom:12px;padding:10px;background:#17243a;border:1px solid #2a4165;border-radius:9px}}
</style></head><body>
<header><div><h1>AHOS Holding Control Center</h1><div class="sub">Local owner console · refresh 5s · {_esc(snapshot["generated_at"])}</div></div>{_badge(str(hb.get("state","unknown")))}</header>
<main>{notice}<div class="grid">{cards}</div>
<div class="section"><h2>Owner Controls</h2><div class="toolbar">
<form method="post" action="/action/start"><button class="neutral">Start / Resume Company</button></form>
<form method="post" action="/action/backup"><button class="neutral">Create Backup</button></form>
<form method="post" action="/action/kill"><button class="kill">KILL SWITCH</button></form>
</div></div>
<div class="section"><h2>Approval Inbox</h2><table><thead><tr><th>Request</th><th>Mission</th><th>Status</th><th>Est. Cost</th><th>Action</th></tr></thead><tbody>{approval_html}</tbody></table></div>
<div class="section"><h2>Mission Queue</h2><table><thead><tr><th>Mission</th><th>Department</th><th>Status</th><th>Attempts</th><th>Objective / Error</th></tr></thead><tbody>{mission_html}</tbody></table></div>
<div class="section"><h2>Coding Supervisor</h2><table><thead><tr><th>Task</th><th>Status</th><th>Attempts</th><th>Blocker / Artifact</th></tr></thead><tbody>{coding_html}</tbody></table></div>
<div class="section"><h2>Virtual Workforce</h2><table><thead><tr><th>Worker</th><th>Department</th><th>Role</th><th>Status</th><th>Last Mission</th><th>Last Stage</th><th>Paid AI</th></tr></thead><tbody>{worker_html}</tbody></table></div>
</main></body></html>'''


def build_handler(state: ControlCenterState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, message: str) -> None:
            self.send_response(303)
            self.send_header("Location", "/?message=" + quote(message))
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/status":
                body = json.dumps(state.snapshot(), indent=2).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/":
                message = parse_qs(parsed.query).get("message", [""])[0]
                body = render_dashboard(state.snapshot(), message).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                form = parse_qs(self.rfile.read(length).decode("utf-8"))
                rid = form.get("request_id", [""])[0]

                if self.path == "/action/approve":
                    if not rid:
                        raise ValueError("request_id required")
                    msg = state.approve(rid)
                elif self.path == "/action/reject":
                    if not rid:
                        raise ValueError("request_id required")
                    msg = state.reject(rid)
                elif self.path == "/action/kill":
                    msg = state.activate_kill_switch()
                elif self.path == "/action/start":
                    msg = state.start_company_service()
                elif self.path == "/action/backup":
                    msg = state.create_backup()
                else:
                    self._send(404, b"not found", "text/plain; charset=utf-8")
                    return
                self._redirect(msg)
            except Exception as exc:
                self._redirect(f"ERROR: {type(exc).__name__}: {exc}")

    return Handler


def serve(state: ControlCenterState, host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("control center must bind to localhost only")
    state.dashboard_pid_path.write_text(str(os.getpid()), encoding="ascii")
    server = ThreadingHTTPServer((host, port), build_handler(state))
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        state.dashboard_pid_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--service-launcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    state = ControlCenterState(
        Path(args.runtime_dir),
        Path(args.service_launcher) if args.service_launcher else None,
    )
    serve(state, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
