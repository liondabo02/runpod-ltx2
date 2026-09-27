from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .autonomous_company import PersistentMissionQueue, QueueStatus
from .coding_supervisor import CodingSupervisorStore, CodingTaskStatus
from .coding_worker import CodingBacklogItem
from .owner_approval import ApprovalStatus, OwnerApprovalInbox
from .studio_executor import execution_status
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
        else:
            candidate = Path(__file__).resolve().parent.parent / "scripts" / "Start-AHOS-CompanyService.ps1"
            if candidate.is_file():
                self.service_launcher = candidate

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
    def repository_root(self) -> Path:
        return self.runtime_dir.parent.resolve()

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
        studio_executions = []
        for ledger in sorted(self.runtime_dir.rglob("EXECUTION-LEDGER.json")):
            try:
                status = execution_status(ledger.parent)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            studio_executions.append({
                "studio_directory": str(ledger.parent),
                "episode_id": status.get("episode_id"),
                "status": status.get("status", "unknown"),
                "spent_usd": status.get("spent_usd", 0),
                "budget_ceiling_usd": status.get("budget_ceiling_usd", 0),
                "stages": status.get("stages", {}),
            })
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
            "studio_executions": studio_executions,
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

    def decide_coding_task(self, task_id: str, *, approved: bool) -> str:
        """Apply and publish an owner-approved coding patch, or reject it.

        The integration is deliberately fail-closed: tracked repository changes,
        modified evidence, a patch that no longer applies, failed tests, or a
        missing upstream all leave the task waiting for owner approval.
        """
        store = CodingSupervisorStore(self.coding_queue_path)
        if not approved:
            store.record_owner_decision(task_id, approved=False)
            return f"coding task rejected: {task_id}"

        task = store.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status is not CodingTaskStatus.WAITING_OWNER_APPROVAL:
            raise ValueError("coding task is not waiting for owner approval")
        if not task.patch_file or not task.approval_file:
            raise ValueError("coding task evidence is incomplete")

        repository = Path(task.repository).resolve()
        patch_file = Path(task.patch_file).resolve()
        if not repository.is_dir() or not (repository / ".git").exists():
            raise ValueError("coding task repository is not a Git working tree")

        def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", "-C", str(repository), *args], text=True,
                capture_output=True, check=check,
            )

        # Untracked runtime output is harmless, but tracked owner changes must
        # never be overwritten or accidentally included in an AI commit.
        if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
            raise ValueError("repository has tracked changes; commit or restore them first")

        approval = json.loads(Path(task.approval_file).read_text(encoding="utf-8"))
        base_commit = str(approval.get("base_commit") or "")
        if not base_commit:
            raise ValueError("approval evidence has no base commit")
        ancestry = git("merge-base", "--is-ancestor", base_commit, "HEAD", check=False)
        if ancestry.returncode != 0:
            raise ValueError("coding task base commit is not an ancestor of HEAD")
        checked = git("apply", "--check", str(patch_file), check=False)
        if checked.returncode:
            already_applied = git(
                "apply", "--reverse", "--check", str(patch_file), check=False,
            )
            if already_applied.returncode == 0:
                store.record_owner_decision(task_id, approved=True)
                return f"coding task was already integrated; approval recorded: {task_id}"
            raise ValueError("coding patch no longer applies cleanly")

        before = git("rev-parse", "HEAD").stdout.strip()
        applied = False
        committed = False
        try:
            git("apply", "--index", str(patch_file))
            applied = True
            changed = tuple(
                line.strip().replace("\\", "/")
                for line in git("diff", "--cached", "--name-only").stdout.splitlines()
                if line.strip()
            )
            expected = tuple(
                str(value).replace("\\", "/")
                for value in approval.get("changed_files", ())
            )
            if not changed or set(changed) != set(expected):
                raise ValueError("staged files do not match owner approval evidence")

            for command in task.test_commands:
                completed = subprocess.run(
                    list(command), cwd=repository, text=True,
                    capture_output=True, check=False,
                )
                if completed.returncode:
                    detail = (completed.stderr or completed.stdout).strip()[-1200:]
                    raise RuntimeError(f"approved test failed: {detail}")

            git("commit", "-m", f"feat(autonomous): {task.title}")
            committed = True
            upstream = git(
                "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                check=False,
            )
            if upstream.returncode or "/" not in upstream.stdout.strip():
                raise ValueError("current branch has no Git upstream")
            remote, branch = upstream.stdout.strip().split("/", 1)
            git("push", remote, f"HEAD:{branch}")
            store.record_owner_decision(task_id, approved=True)
            return f"coding task approved, tested, committed and pushed: {task_id}"
        except Exception:
            # Nothing is removed from runtime and untracked files are preserved.
            # Only this transaction's tracked/index changes are rolled back.
            if committed:
                git("reset", "--hard", before, check=False)
            elif applied:
                git("reset", "--hard", "HEAD", check=False)
            raise

    def create_coding_task(self, objective: str, scope: str = "core") -> str:
        objective = " ".join(objective.split()).strip()
        if not objective:
            raise ValueError("task objective is required")
        if len(objective) > 4000:
            raise ValueError("task objective is too long")
        scopes = {
            "core": ("ahos_core",),
            "github": (".github",),
            "docs": ("README.md", "ahos_core/docs"),
        }
        if scope not in scopes:
            raise ValueError("unknown coding task scope")
        repository = self.repository_root
        if not (repository / ".git").exists():
            raise ValueError("runtime directory is not inside the AHOS Git repository")
        task_id = f"CODE-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        test_command = (
            str(Path(sys.executable).resolve()), "-m", "pytest", "-q", "ahos_core/tests",
        )
        CodingSupervisorStore(self.coding_queue_path).enqueue(
            CodingBacklogItem(
                task_id=task_id,
                title=objective,
                repository=repository,
                base_ref="HEAD",
                allowed_paths=scopes[scope],
                test_commands=(test_command,),
            ),
            idempotency_key=f"panel:{task_id}",
            max_attempts=2,
            priority=10,
        )
        return f"coding task queued: {task_id}"

    def coding_review(self, task_id: str) -> dict[str, object]:
        task = CodingSupervisorStore(self.coding_queue_path).get(task_id)
        if task is None:
            raise KeyError(task_id)
        approval: dict[str, object] = {}
        patch = ""
        if task.approval_file and Path(task.approval_file).is_file():
            approval = json.loads(Path(task.approval_file).read_text(encoding="utf-8"))
        if task.patch_file and Path(task.patch_file).is_file():
            patch = Path(task.patch_file).read_text(encoding="utf-8", errors="replace")
            if len(patch) > 250_000:
                patch = patch[:250_000] + "\n[patch display truncated]"
        return {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status.value,
            "repository": task.repository,
            "allowed_paths": task.allowed_paths,
            "test_commands": task.test_commands,
            "approval": approval,
            "patch": patch,
        }

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


def render_coding_review(review: dict[str, object]) -> str:
    tests = "\n".join(" ".join(command) for command in review["test_commands"]) or "No tests declared"
    approval = json.dumps(review["approval"], indent=2, ensure_ascii=False)
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS Code Review</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#0b1020;color:#e9eefc;margin:0;padding:24px}}
a{{color:#7aa2ff}} .panel{{background:#141b2d;border:1px solid #26324b;border-radius:12px;padding:18px;margin-top:16px}}
pre{{white-space:pre-wrap;word-break:break-word;background:#090d18;padding:16px;border-radius:8px;overflow:auto}}
.badge{{color:#f6c85f}} button{{border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer}}
.approve{{background:#33d17a}} .reject{{background:#ff6b6b}} form{{display:inline;margin-right:8px}}
</style></head><body><a href="/">← Control Center</a>
<h1>{_esc(review["task_id"])}</h1><p>{_esc(review["title"])}</p>
<div class="panel"><b>Status:</b> <span class="badge">{_esc(review["status"])}</span><br>
<b>Allowed paths:</b> {_esc(", ".join(review["allowed_paths"]))}</div>
<div class="panel"><h2>Approved tests</h2><pre>{_esc(tests)}</pre></div>
<div class="panel"><h2>Approval evidence</h2><pre>{_esc(approval)}</pre></div>
<div class="panel"><h2>Proposed patch</h2><pre>{_esc(review["patch"] or "Patch not generated yet.")}</pre></div>
{('<div class="panel"><form method="post" action="/action/code-approve"><input type="hidden" name="task_id" value="' + _esc(review["task_id"]) + '"><button class="approve">Approve &amp; Publish</button></form><form method="post" action="/action/code-reject"><input type="hidden" name="task_id" value="' + _esc(review["task_id"]) + '"><button class="reject">Reject</button></form></div>') if review["status"] == "waiting_owner_approval" else ""}
</body></html>'''


def render_dashboard(snapshot: dict[str, object], message: str = "") -> str:
    hb = snapshot["heartbeat"]
    counts = snapshot["mission_counts"]
    coding = snapshot.get("coding_supervisor", {"counts": {}, "tasks": []})
    coding_counts = coding.get("counts", {})
    studio_executions = snapshot.get("studio_executions", [])

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
            ("Studio Executions", len(studio_executions)),
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

    coding_rows = []
    for t in coding.get("tasks", []):
        actions = "-"
        review_link = f'<a href="/coding/{quote(str(t["task_id"]))}">Review</a>'
        if t["status"] == "waiting_owner_approval":
            tid = _esc(t["task_id"])
            actions = (
                '<form class="inline" method="post" action="/action/code-approve">'
                f'<input type="hidden" name="task_id" value="{tid}">'
                '<button class="approve">Approve &amp; Publish</button></form>'
                '<form class="inline" method="post" action="/action/code-reject">'
                f'<input type="hidden" name="task_id" value="{tid}">'
                '<button class="reject">Reject</button></form>'
            )
        coding_rows.append(
            f'<tr><td>{_esc(t["task_id"])}</td><td>{_badge(t["status"])}</td>'
            f'<td>{_esc(str(t["attempts"]) + "/" + str(t["max_attempts"]))}</td>'
            f'<td class="wide">{_esc(t["last_error"] or t["patch_file"] or t["title"])}</td>'
            f'<td>{review_link} &nbsp; {actions}</td></tr>'
        )
    coding_html = "".join(coding_rows) or '<tr><td colspan="5">No coding tasks yet.</td></tr>'

    studio_html = "".join(
        f'<tr><td>{_esc(item.get("episode_id") or "-")}</td>'
        f'<td>{_badge(str(item.get("status", "unknown")))}</td>'
        f'<td>${float(item.get("spent_usd", 0)):.4f} / ${float(item.get("budget_ceiling_usd", 0)):.4f}</td>'
        f'<td class="wide">{_esc(", ".join(name + ":" + str(stage.get("status")) for name, stage in item.get("stages", {}).items()))}</td></tr>'
        for item in studio_executions
    ) or '<tr><td colspan="4">No studio execution initialized.</td></tr>'

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
<div class="section"><h2>Create Coding Task</h2><form method="post" action="/action/code-create" class="task-form">
<div class="toolbar"><input name="objective" maxlength="4000" required placeholder="Describe the result you want..." style="flex:1;min-width:320px;padding:10px;border-radius:8px;border:1px solid var(--line)">
<select name="scope" style="padding:10px;border-radius:8px"><option value="core">Core system</option><option value="github">GitHub automation</option><option value="docs">Documentation</option></select>
<button class="neutral">Queue Task</button></div></form></div>
<div class="section"><h2>Approval Inbox</h2><table><thead><tr><th>Request</th><th>Mission</th><th>Status</th><th>Est. Cost</th><th>Action</th></tr></thead><tbody>{approval_html}</tbody></table></div>
<div class="section"><h2>Mission Queue</h2><table><thead><tr><th>Mission</th><th>Department</th><th>Status</th><th>Attempts</th><th>Objective / Error</th></tr></thead><tbody>{mission_html}</tbody></table></div>
<div class="section"><h2>Coding Supervisor</h2><table><thead><tr><th>Task</th><th>Status</th><th>Attempts</th><th>Blocker / Artifact</th><th>Owner Action</th></tr></thead><tbody>{coding_html}</tbody></table></div>
<div class="section"><h2>Studio Execution</h2><table><thead><tr><th>Episode</th><th>Status</th><th>Cost / Budget</th><th>Stages</th></tr></thead><tbody>{studio_html}</tbody></table></div>
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
            if parsed.path.startswith("/coding/"):
                task_id = parsed.path.removeprefix("/coding/")
                body = render_coding_review(state.coding_review(task_id)).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                form = parse_qs(self.rfile.read(length).decode("utf-8"))
                rid = form.get("request_id", [""])[0]
                task_id = form.get("task_id", [""])[0]
                objective = form.get("objective", [""])[0]
                scope = form.get("scope", ["core"])[0]

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
                elif self.path == "/action/code-approve":
                    if not task_id:
                        raise ValueError("task_id required")
                    msg = state.decide_coding_task(task_id, approved=True)
                elif self.path == "/action/code-reject":
                    if not task_id:
                        raise ValueError("task_id required")
                    msg = state.decide_coding_task(task_id, approved=False)
                elif self.path == "/action/code-create":
                    msg = state.create_coding_task(objective, scope)
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
