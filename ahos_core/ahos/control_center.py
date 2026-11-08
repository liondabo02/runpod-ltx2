from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sqlite3
import subprocess
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .autonomous_company import PersistentMissionQueue, QueueStatus
from .owner_approval import ApprovalStatus, OwnerApprovalInbox
from .owner_console import ConsoleResult, OwnerConsole, build_default_console
from .office_view import build_office_model, render_office
from .outputs import (
    build_output_index,
    project_documents,
    render_document_page,
    render_outputs_page,
    resolve_output_file,
)
from .virtual_workforce import default_virtual_workforce


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ControlCenterState:
    runtime_dir: Path
    service_launcher: Path | None = None
    console: OwnerConsole | None = None
    growth_loop: object | None = field(default=None, repr=False, compare=False)
    growth_thread: threading.Thread | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self.runtime_dir = Path(self.runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self.service_launcher is not None:
            self.service_launcher = Path(self.service_launcher)
        if self.console is None:
            self.console = build_default_console(self.runtime_dir)
        try:
            from . import live_activity

            live_activity.configure(self.runtime_dir / "live-events.jsonl")
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            from .recovery import recover

            recover(self.runtime_dir, self.console.queue)
        except Exception:  # pragma: no cover - startup must not crash
            pass


    @property
    def queue_db(self) -> Path:
        return self.runtime_dir / "company-service.db"

    @property
    def commands_log(self) -> Path:
        return self.runtime_dir / "owner-commands.jsonl"

    @property
    def departments_json(self) -> Path:
        return self.runtime_dir / "departments.json"

    @property
    def approvals_db(self) -> Path:
        return self.runtime_dir / "owner-approvals.db"

    @property
    def heartbeat_path(self) -> Path:
        return self.runtime_dir / "company-service-heartbeat.json"

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
        profiles = (
            self.console.book.worker_profiles()
            if self.console is not None
            else default_virtual_workforce()
        )
        workers = []
        for profile in profiles:
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
            "departments": self.departments(),
            "projects": self.projects(),
            "ceo": self.ceo_brief(),
            "autonomy": self.autonomy_runner().status(),
            "autonomy_actions": self.autonomy_actions(),
            "mission_history": self.mission_history(),
            "worker_quality": self.worker_quality(),
            "project_locks": self.project_locks(),
            "panel_token": self.panel_token,
            "last_command": self.last_command(),
            "growth": self.growth_status(),
            "kill_switch_active": self.stop_path.exists(),
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

    def handle_command(self, text: str) -> str:
        """Run one owner command and append it to the command journal."""

        if self.console is None:
            return "owner console is not configured"

        result: ConsoleResult = self.console.handle(text)
        record = {
            "at": _utc_now(),
            "command": text,
            "kind": result.kind.value,
            "status": result.status,
            "department_id": result.department_id,
            "message": result.message,
        }
        with self.commands_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return result.message

    # ------------------------------------------------------------ growth loop
    def growth_status(self) -> dict[str, object]:
        stop_file = self.runtime_dir / "growth-loop.stop"
        alive = bool(self.growth_thread and self.growth_thread.is_alive())
        running = alive and not stop_file.exists()
        detail = (
            self.growth_loop.status()
            if self.growth_loop is not None
            else {"ticks": 0, "last": None, "interval_seconds": 0}
        )
        return {"running": running, **detail}

    def start_growth_loop(
        self,
        interval_seconds: float = 30.0,
        missions_per_tick: int = 1,
    ) -> str:
        if self.growth_thread is not None and self.growth_thread.is_alive():
            return "gelişim döngüsü zaten çalışıyor"
        if self.console is None:
            return "owner console is not configured"

        from .growth_loop import GrowthLoop

        stop_file = self.runtime_dir / "growth-loop.stop"
        stop_file.unlink(missing_ok=True)

        loop = GrowthLoop(
            self.console,
            interval_seconds=max(1.0, interval_seconds),
            missions_per_tick=max(1, missions_per_tick),
            stop_file=stop_file,
        )
        thread = threading.Thread(
            target=loop.run,
            name="ahos-growth-loop",
            daemon=True,
        )
        self.growth_loop = loop
        self.growth_thread = thread
        thread.start()
        return (
            "gelişim döngüsü başladı: her "
            f"{int(max(1.0, interval_seconds))} sn'de "
            f"{max(1, missions_per_tick)} departman görevi"
        )

    def stop_growth_loop(self) -> str:
        stop_file = self.runtime_dir / "growth-loop.stop"
        was_running = bool(self.growth_thread and self.growth_thread.is_alive())
        stop_file.write_text(_utc_now(), encoding="utf-8")
        if self.growth_thread is not None:
            self.growth_thread.join(timeout=5)
        return (
            "gelişim döngüsü durduruldu"
            if was_running
            else "gelişim döngüsü zaten duruyor"
        )

    def systems_status(self) -> list[dict[str, object]]:
        """One-screen status of every subsystem the holding depends on."""

        import urllib.request

        rows: list[dict[str, object]] = []
        try:
            counts = self.snapshot()["mission_counts"]
            rows.append(
                {
                    "name": "AHOS kuyruğu",
                    "state": f"pending {counts.get('pending', 0)} · "
                    f"running {counts.get('running', 0)} · "
                    f"blocked {counts.get('blocked', 0)}",
                    "detail": f"runtime: {self.runtime_dir}",
                }
            )
        except Exception:  # noqa: BLE001
            rows.append({"name": "AHOS kuyruğu", "state": "okunamadı", "detail": ""})

        ruflo_cli = Path(r"C:\AHOS\tools\ruflo\node_modules\ruflo\bin\ruflo.js")
        queue = self.runtime_dir / "ruflo-queue"
        results = self.runtime_dir / "ruflo-results"
        queued = len(list(queue.glob("*.json"))) if queue.exists() else 0
        done = len(list(results.glob("*.json"))) if results.exists() else 0
        worker_pid_file = self.runtime_dir / "ruflo-worker.pid"
        worker_pid = ""
        if worker_pid_file.exists():
            worker_pid = worker_pid_file.read_text(encoding="utf-8", errors="ignore").strip()
        worker_alive = _pid_alive(worker_pid)
        rows.append(
            {
                "name": "Ruflo (planlayıcı)",
                "state": (
                    f"kurulu · kuyruk {queued} · sonuç {done} · worker "
                    + ("çalışıyor" if worker_alive else "kapalı")
                    if ruflo_cli.exists()
                    else "kurulu değil"
                ),
                "detail": f"CLI: {ruflo_cli} · worker pid: {worker_pid or '-'}",
            }
        )

        tunnel = "kapalı"
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:11500/api/tags", timeout=1.5
            ) as response:
                tunnel = f"açık ({response.status})"
        except Exception:  # noqa: BLE001
            tunnel = "kapalı"
        rows.append(
            {
                "name": "Oracle tünel modeli",
                "state": tunnel,
                "detail": "http://127.0.0.1:11500 (qwen2.5-coder)",
            }
        )

        try:
            from .adapters import runpod

            pod = runpod.status(self.runtime_dir)
            rows.append(
                {
                    "name": "RunPod (GPU/video)",
                    "state": (
                        f"{pod['state']} · kuyruk {pod['queued']} · sonuç {pod['results']}"
                    ),
                    "detail": "AHOS_RUNPOD_ENABLED=1 + AHOS_RUNPOD_ENDPOINT ile açılır",
                }
            )
        except Exception:  # noqa: BLE001
            rows.append(
                {"name": "RunPod (GPU/video)", "state": "okunamadı", "detail": ""}
            )
        try:
            from .providers import default_chain, probe

            checks = [
                f"{provider.name}={'ok' if probe(provider, timeout=2.5) else 'yok'}"
                for provider in default_chain()
            ]
            rows.append(
                {
                    "name": "Model sağlayıcı zinciri",
                    "state": " · ".join(checks),
                    "detail": "aktif: "
                    + (os.environ.get("AHOS_ACTIVE_PROVIDER") or "seçilmedi"),
                }
            )
        except Exception:  # noqa: BLE001
            rows.append(
                {"name": "Model sağlayıcı zinciri", "state": "ölçülemedi", "detail": ""}
            )
        return rows

    def panel_directory(self) -> list[dict[str, object]]:
        """Known local panels/offices, with a short live health probe."""

        import urllib.request

        candidates = [
            ("Başkanlık paneli (üretim)", "http://127.0.0.1:8766/"),
            ("Canlı ofis", "http://127.0.0.1:8766/office"),
            ("Ofis sunucusu (ayrı)", "http://127.0.0.1:8799/"),
            ("Q99 panel — browser", "http://127.0.0.1:18765/"),
            ("Q99 panel — dashboard", "http://127.0.0.1:18766/"),
        ]
        rows: list[dict[str, object]] = []
        for label, url in candidates:
            status = "kapalı"
            try:
                with urllib.request.urlopen(url, timeout=1.5) as response:
                    status = f"açık ({response.status})"
            except Exception:  # noqa: BLE001 - probe only
                status = "kapalı"
            rows.append({"label": label, "url": url, "status": status})
        return rows

    def mission_history(self, limit: int = 10) -> list[dict[str, object]]:
        from .autonomous_company import PersistentMissionQueue

        queue = PersistentMissionQueue(self.queue_db)
        rows: list[dict[str, object]] = []
        for mission in queue.list()[-limit:][::-1]:
            qa = None
            if mission.result_json:
                try:
                    payload = json.loads(mission.result_json)
                except json.JSONDecodeError:
                    payload = {}
                for step in payload.get("steps") or ():
                    if step.get("qa_summary"):
                        qa = str(step["qa_summary"])[:160]
                        break
            duration = "ölçülmedi"
            try:
                started = datetime.fromisoformat(mission.created_at)
                finished = datetime.fromisoformat(mission.updated_at)
                duration = f"{(finished - started).total_seconds():.2f}s"
            except (ValueError, TypeError):
                pass
            rows.append(
                {
                    "mission_id": mission.mission_id,
                    "department": mission.primary_department,
                    "status": mission.status.value,
                    "duration": duration,
                    "qa": qa,
                    "error": (mission.last_error or "")[:160],
                    "cost": "ölçülmedi",
                }
            )
        return rows

    def autonomy_runner(self):
        from .autonomy import AutonomyLimits, AutonomyRunner

        return AutonomyRunner(
            self.console,
            self.runtime_dir,
            limits=AutonomyLimits(max_missions=1),
        )

    @property
    def panel_token(self) -> str:
        path = self.runtime_dir / "panel-token.txt"
        if not path.exists():
            import secrets

            path.write_text(secrets.token_urlsafe(24), encoding="utf-8")
        return path.read_text(encoding="utf-8").strip()

    def worker_quality(self, limit: int = 8) -> list[dict[str, object]]:
        from .worker_metrics import summary

        rows = [
            {"worker_id": worker, **values}
            for worker, values in summary(self.runtime_dir).items()
        ]
        rows.sort(key=lambda row: (-int(row["runs"]), str(row["worker_id"])))
        return rows[:limit]

    def project_locks(self) -> list[dict[str, object]]:
        from .project_locks import list_held

        return list_held()

    def autonomy_actions(self, limit: int = 10) -> list[dict[str, object]]:
        path = self.runtime_dir / "autonomy-actions.jsonl"
        if not path.exists():
            return []
        entries: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries[-limit:]

    def autonomy_control(self, action: str, token: str, client: str) -> str:
        if client not in {"127.0.0.1", "::1"}:
            raise PermissionError("yerel olmayan istek reddedildi")
        if token.strip() != self.panel_token:
            raise PermissionError("geçersiz panel token")

        runner = self.autonomy_runner()
        if action == "pause":
            runner.pause()
            return "otonomi duraklatıldı"
        if action == "resume":
            runner.resume()
            return "otonomi devam ediyor"
        if action == "stop":
            runner.stop()
            return "otonomi acil durduruldu"
        if action == "start":
            runner.resume()
            from .autoschedule import AutoLimits, BoundedScheduler

            limits = AutoLimits(
                max_missions_per_hour=6,
                max_missions_total=3,
                idle_sleep_seconds=0.0,
            )
            scheduler = BoundedScheduler(
                runner,
                self.runtime_dir,
                limits=limits,
                sleep=lambda seconds: None,
            )
            outcomes = scheduler.run(max_ticks=limits.max_missions_total)
            runner._log_action("start", ",".join(outcomes))
            state = scheduler.state
            return (
                f"otonomi başlatıldı: {', '.join(outcomes)} "
                f"(bu saat {state.missions_this_hour}/{limits.max_missions_per_hour}, "
                f"oturum {state.missions_total}/{limits.max_missions_total}, "
                f"ücretli 0 USD)"
            )
        raise ValueError(f"bilinmeyen işlem: {action}")

    def autonomy_status(self) -> dict[str, object]:
        path = self.runtime_dir / "autonomy-state.json"
        if not path.exists():
            return {"status": "never-run", "executed": 0, "failed": 0, "paid_calls": 0}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "unknown", "executed": 0, "failed": 0, "paid_calls": 0}
        payload["paid_calls"] = 0
        return payload

    def ceo_brief(self) -> dict[str, object]:
        if self.console is None:
            return {}
        from .holding_office import HoldingOffice

        office = HoldingOffice(self.console)
        return {"text": office.brief(), **office.status()}

    def office_model(self) -> dict[str, object]:
        if self.console is None:
            return {"rooms": [], "stats": {}, "ticker": []}
        return build_office_model(
            self.console.book,
            PersistentMissionQueue(self.queue_db),
        )

    def output_index(self):
        if self.console is None:
            return ()
        return build_output_index(
            self.console.artifacts_root,
            PersistentMissionQueue(self.queue_db),
        )

    def project_documents(self) -> list[dict[str, object]]:
        return project_documents(self.runtime_dir / "projects.json")

    def resolve_project_document(self, project_id: str, filename: str) -> Path:
        if self.console is None or self.console.projects is None:
            raise FileNotFoundError(project_id)
        link = self.console.projects.require(project_id)
        root = link.path.resolve()
        candidate = (root / filename).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise ValueError("project document not allowed")
        if candidate.suffix.lower() not in {".md", ".txt", ".json"}:
            raise ValueError("unsupported document type")
        return candidate

    def last_command(self) -> dict[str, object] | None:
        if not self.commands_log.exists():
            return None
        lines = [
            line
            for line in self.commands_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not lines:
            return None
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def department_execution(self, ident: str) -> dict[str, object]:
        if self.console is None:
            return dict(state="unavailable", summary="Yönetici bağlı değil", production_ready=False)
        if self.console._explicit_executors:
            return dict(state="custom_unverified", summary="Özel yürütücü; kapsamı ayrıca doğrulanmalı", production_ready=False)
        project = self.console._project_for_department(ident)
        if project is not None:
            from .code_work import detect_web_root
            if not (detect_web_root(project.path) / "index.html").is_file():
                return dict(state="unsupported_project", summary="Proje bağlı; doğrulanmış web yürütücüsüne uygun değil", production_ready=False)
            return dict(state="web_executor_bound", summary="Web bakım yürütücüsü ve bağımsız statik QA bağlı; genel ürün üretimi doğrulanmadı", production_ready=False)
        if ident == "guvenlik":
            return dict(state="scanner_bound", summary="Yerel depo güvenlik tarayıcısı bağlı", production_ready=False)
        return dict(state="not_bound", summary="Üretim yürütücüsü bağlı değil; kadro tanımı mevcut", production_ready=False)

    def departments(self) -> list[dict[str, object]]:
        if self.console is None:
            return []
        return [
            {
                "department_id": spec.department_id,
                "name": spec.name,
                "workers": len(spec.workers),
                "capabilities": len(spec.capabilities),
                "status": spec.status,
                "source": spec.source,
                "execution": self.department_execution(spec.department_id),
            }
            for spec in self.console.book.all()
        ]

    def projects(self) -> list[dict[str, object]]:
        if self.console is None or self.console.projects is None:
            return []
        return [
            {
                "project_id": link.project_id,
                "name": link.name,
                "department_id": link.department_id,
                "kind": link.kind,
                "path": str(link.path),
                "created_at": link.created_at,
            }
            for link in self.console.projects.all()
        ]

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


def _pid_alive(pid_text: str) -> bool:
    """True when the process exists. Never signals the process itself."""

    try:
        pid = int(str(pid_text).strip())
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def render_systems_page(rows: list[dict[str, object]]) -> str:
    body = "".join(
        f'<tr><td><b>{_esc(str(row["name"]))}</b></td>'
        f'<td>{_esc(str(row["state"]))}</td>'
        f'<td class="wide">{_esc(str(row["detail"]))}</td></tr>'
        for row in rows
    ) or '<tr><td colspan="3">Kayıt yok.</td></tr>'
    nav = (
        '<nav class="nav"><a href="/">Panel</a><a href="/office">Canlı Ofis</a>'
        '<a href="/panels">Paneller</a>'
        '<a href="/systems">Sistemler</a><a href="/outputs">Çıktılar</a></nav>'
    )
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS — Sistemler</title>
<style>
body{{background:#0b1020;color:#e9eefc;font-family:system-ui,Segoe UI,sans-serif;margin:0}}
.nav{{display:flex;gap:16px;padding:12px 24px;background:#101830;border-bottom:1px solid #26324b}}
.nav a{{color:#7aa2ff;text-decoration:none;font-size:14px}}
main{{padding:24px}}
table{{width:100%;border-collapse:collapse;background:#141b2d;border-radius:12px;overflow:hidden}}
th,td{{padding:12px 14px;border-bottom:1px solid #26324b;text-align:left;font-size:14px}}
th{{color:#9cabca}}
.wide{{color:#9cabca;word-break:break-all}}
</style></head><body>
{nav}
<main><h1>Holding alt sistemleri</h1>
<p style="color:#9cabca">Tek panelden izlenen gerçek durum; ölçülmeyen değer uydurulmaz.</p>
<table><thead><tr><th>Bileşen</th><th>Durum</th><th>Ayrıntı</th></tr></thead>
<tbody>{body}</tbody></table></main></body></html>"""


def render_panels_page(rows: list[dict[str, object]]) -> str:
    body = "".join(
        f'<tr><td>{_esc(str(row["label"]))}</td>'
        f'<td><a href="{_esc(str(row["url"]))}">{_esc(str(row["url"]))}</a></td>'
        f'<td>{_esc(str(row["status"]))}</td></tr>'
        for row in rows
    ) or '<tr><td colspan="3">Kayıt yok.</td></tr>'
    nav = (
        '<nav class="nav"><a href="/">Panel</a><a href="/office">Canlı Ofis</a>'
        '<a href="/outputs">Çıktılar</a><a href="/panels">Paneller</a></nav>'
    )
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS — Paneller</title>
<style>
body{{background:#0b1020;color:#e9eefc;font-family:system-ui,Segoe UI,sans-serif;margin:0}}
.nav{{display:flex;gap:16px;padding:12px 24px;background:#101830;border-bottom:1px solid #26324b}}
.nav a{{color:#7aa2ff;text-decoration:none;font-size:14px}}
main{{padding:24px}}
table{{width:100%;border-collapse:collapse;background:#141b2d;border-radius:12px;overflow:hidden}}
th,td{{padding:10px 14px;border-bottom:1px solid #26324b;text-align:left;font-size:14px}}
th{{color:#9cabca;font-weight:600}}
a{{color:#7aa2ff}}
</style></head><body>
{nav}
<main><h1>Paneller ve ofisler</h1>
<p style="color:#9cabca">Tek üretim paneli: <b>8766</b>. Diğerleri salt izleme/deneme.</p>
<table><thead><tr><th>Panel</th><th>Adres</th><th>Durum</th></tr></thead>
<tbody>{body}</tbody></table></main></body></html>"""


def render_dashboard(snapshot: dict[str, object], message: str = "") -> str:
    hb = snapshot["heartbeat"]
    counts = snapshot["mission_counts"]

    nav = (
        '<nav class="nav">'
        '<a href="/">Panel</a>'
        '<a href="/office">Canlı Ofis</a>'
        '<a href="/agent-office">Ajan Ofisi</a>'
        '<a href="/outputs">Çıktılar</a>'
        '<a href="/panels">Paneller</a>'
        '<a href="/systems">Sistemler</a>'
        '<a href="/api/status">API</a>'
        "</nav>"
    )

    cards = "".join(
        f'<div class="card"><div class="label">{_esc(k)}</div><div class="value">{_esc(v)}</div></div>'
        for k, v in (
            ("Service", hb.get("state", "unknown")),
            ("Workers", snapshot["worker_count"]),
            ("Running", counts.get("running", 0)),
            ("Queued", counts.get("pending", 0)),
            ("Waiting Approval", snapshot["waiting_approval_count"]),
            ("Blocked / Failed", counts.get("blocked", 0) + counts.get("failed", 0)),
            ("Departmanlar", len(snapshot.get("departments") or ())),
            (
                "Gelişim Döngüsü",
                "AÇIK" if (snapshot.get("growth") or {}).get("running") else "KAPALI",
            ),
            (
                "Otonomi",
                (snapshot.get("autonomy") or {}).get("status", "-"),
            ),
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

    notice = f'<div class="notice">{_esc(message)}</div>' if message else ""

    last_command = snapshot.get("last_command") or {}
    last_html = ""
    if last_command:
        last_html = (
            '<div class="lastcmd">'
            f'<span class="label">Son komut</span> '
            f'<code>{_esc(last_command.get("command"))}</code> '
            f'{_badge(str(last_command.get("status")))}'
            f'<div class="lastmsg">{_esc(last_command.get("message"))}</div>'
            "</div>"
        )

    department_html = "".join(
        f'<tr><td>{_esc(d["department_id"])}</td><td>{_esc(d["name"])}</td>'
        f'<td>{_esc(d["workers"])}</td><td>{_esc(d["capabilities"])}</td>'
        f'<td>{_badge(str(d["status"]))}</td><td>{_esc(d["source"])}</td>'
        f'<td>{_esc((d.get("execution") or {}).get("summary", "Ölçülmedi"))}</td></tr>'
        for d in snapshot.get("departments") or ()
    ) or '<tr><td colspan="6">No departments yet.</td></tr>'

    project_html = "".join(
        f'<tr><td>{_esc(p["project_id"])}</td><td>{_esc(p["name"])}</td>'
        f'<td>{_esc(p["department_id"])}</td><td>{_esc(p["kind"])}</td>'
        f'<td class="wide">{_esc(p["path"])}</td></tr>'
        for p in snapshot.get("projects") or ()
    ) or '<tr><td colspan="5">Bağlı proje yok.</td></tr>'

    ceo = snapshot.get("ceo") or {}
    ceo_html = f'<div class="ceo"><pre>{_esc(ceo.get("text") or "")}</pre></div>'

    workers_html = "".join(
        f'<tr><td>{_esc(w["worker_id"])}</td><td>{int(w["runs"])}</td>'
        f'<td>{float(w["success_rate"]) * 100:.0f}%</td>'
        f'<td>{int(w.get("reassignments", 0))}</td>'
        f'<td>{float(w["avg_ms"]):.0f} ms</td>'
        f'<td class="wide">{_esc(w["last_error"] or "-")}</td></tr>'
        for w in snapshot.get("worker_quality") or ()
    ) or '<tr><td colspan="6">Henüz ölçülmüş işçi çalışması yok.</td></tr>'

    locks_html = "".join(
        f'<li><b>{_esc(str(lock.get("mission_id") or "unknown-owner"))}</b> · '
        f'pid {_esc(str(lock.get("pid") or "?"))} · '
        f'{_esc(str(lock.get("acquired_at") or "-"))}</li>'
        for lock in snapshot.get("project_locks") or ()
    ) or "<li>Kilitli proje yok.</li>"

    history_html = "".join(
        f'<tr><td class="wide">{_esc(h["mission_id"][:44])}</td>'
        f'<td>{_esc(h["department"])}</td><td>{_badge(str(h["status"]))}</td>'
        f'<td>{_esc(h["duration"])}</td><td class="wide">{_esc(h["qa"] or "ölçülmedi")}</td>'
        f'<td class="wide">{_esc(h["error"] or "-")}</td><td>{_esc(h["cost"])}</td></tr>'
        for h in snapshot.get("mission_history") or ()
    ) or '<tr><td colspan="7">Kayıt yok.</td></tr>'

    return f'''<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS Holding Control Center</title>
<style>
.nav{{display:flex;gap:16px;padding:12px 24px;background:#101830;border-bottom:1px solid var(--line)}}
.nav a{{color:var(--accent);text-decoration:none;font-size:14px}}
.nav a:hover{{text-decoration:underline}}
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
.command{{display:flex;gap:10px;padding:14px;flex-wrap:wrap}}
.command textarea{{flex:1;min-width:280px;min-height:58px;resize:vertical;background:#0e1526;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:10px;font:inherit}}
.accent{{background:var(--accent);color:#08122b}}
.lastcmd{{padding:0 14px 14px;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.lastcmd code{{background:#0e1526;border:1px solid var(--line);border-radius:6px;padding:3px 7px;color:var(--text)}}
.lastmsg{{flex-basis:100%;color:var(--text)}}
.ceo{{padding:14px 16px}} .ceo pre{{margin:0;white-space:pre-wrap;font:13px/1.6 Consolas,monospace;color:#c9d6f2}}
</style></head><body>
{nav}
<header><div><h1>AHOS Holding Control Center</h1><div class="sub">Local owner console · refresh 5s · {_esc(snapshot["generated_at"])} · <a href="/office" style="color:var(--accent)">Ofis →</a> · <a href="/outputs" style="color:var(--accent)">Çıktılar →</a></div></div>{_badge(str(hb.get("state","unknown")))}</header>
<main>{notice}<div class="grid">{cards}</div><div class="section"><h2>Sahip Komutu — Holding</h2>
<form class="command" method="post" action="/action/command">
<textarea id="cmd" name="command" placeholder="ör. çizgi film departmanı kur · yazılım şirketi kur · landing page yap · durum" required></textarea>
<button class="accent">Gönder</button>
</form>{last_html}</div>
<div class="section"><h2>Holding Yönetimi (CEO)</h2>{ceo_html}</div>
<div class="section"><h2>Departmanlar</h2><table><thead><tr><th>ID</th><th>Ad</th><th>Ajan</th><th>Yetkinlik</th><th>Kayıt durumu</th><th>Kaynak</th><th>Gerçek yürütme kapsamı</th></tr></thead><tbody>{department_html}</tbody></table></div>
<div class="section"><h2>Projeler</h2><table><thead><tr><th>ID</th><th>Ad</th><th>Departman</th><th>Tür</th><th>Yol</th></tr></thead><tbody>{project_html}</tbody></table></div>
<div class="section"><h2>Otonomi Kontrolleri</h2><div class="toolbar">
<form method="post" action="/action/autonomy/start"><input type="hidden" name="token" value="{_esc(snapshot.get("panel_token", ""))}"><button class="neutral">Başlat</button></form>
<form method="post" action="/action/autonomy/pause"><input type="hidden" name="token" value="{_esc(snapshot.get("panel_token", ""))}"><button class="neutral">Duraklat</button></form>
<form method="post" action="/action/autonomy/resume"><input type="hidden" name="token" value="{_esc(snapshot.get("panel_token", ""))}"><button class="neutral">Devam Ettir</button></form>
<form method="post" action="/action/autonomy/stop"><input type="hidden" name="token" value="{_esc(snapshot.get("panel_token", ""))}"><button class="kill">ACİL DURDUR</button></form>
<div style="align-self:center;color:var(--muted);font-size:13px">durum: <b>{_esc((snapshot.get("autonomy") or {}).get("status", "-"))}</b> · ücretli çağrı: 0</div>
</div></div>
<div class="section"><h2>Proje Kilitleri</h2><ul>{locks_html}</ul></div>
<div class="section"><h2>İşçi Kalitesi (gerçek kayıtlar)</h2><table><thead><tr><th>Ajan</th><th>Görev</th><th>Başarı</th><th>Yeniden atama</th><th>Ort. süre</th><th>Son hata</th></tr></thead><tbody>{workers_html}</tbody></table></div>
<div class="section"><h2>Görev Geçmişi (gerçek kayıtlar)</h2><table><thead><tr><th>Görev</th><th>Departman</th><th>Durum</th><th>Süre</th><th>QA</th><th>Hata</th><th>Maliyet</th></tr></thead><tbody>{history_html}</tbody></table></div>
<div class="section"><h2>Owner Controls</h2><div class="toolbar">
<form method="post" action="/action/start"><button class="neutral">Start / Resume Company</button></form>
<form method="post" action="/action/loop-start"><button class="neutral">Gelişim Döngüsü Başlat</button></form>
<form method="post" action="/action/loop-stop"><button class="neutral">Döngüyü Durdur</button></form>
<form method="post" action="/action/backup"><button class="neutral">Create Backup</button></form>
<form method="post" action="/action/kill"><button class="kill">KILL SWITCH</button></form>
<a href="/office" style="align-self:center;color:var(--accent);text-decoration:none;font-weight:650">Ofis →</a>
<a href="/outputs" style="align-self:center;color:var(--accent);text-decoration:none;font-weight:650">Çıktılar →</a>
</div></div>
<div class="section"><h2>Approval Inbox</h2><table><thead><tr><th>Request</th><th>Mission</th><th>Status</th><th>Est. Cost</th><th>Action</th></tr></thead><tbody>{approval_html}</tbody></table></div>
<div class="section"><h2>Mission Queue</h2><table><thead><tr><th>Mission</th><th>Department</th><th>Status</th><th>Attempts</th><th>Objective / Error</th></tr></thead><tbody>{mission_html}</tbody></table></div>
<div class="section"><h2>Virtual Workforce</h2><table><thead><tr><th>Worker</th><th>Department</th><th>Role</th><th>Status</th><th>Last Mission</th><th>Last Stage</th><th>Paid AI</th></tr></thead><tbody>{worker_html}</tbody></table></div>
</main>
<script>
(function(){{
  var box = document.getElementById('cmd');
  function safeToRefresh(){{
    var active = document.activeElement;
    if (active && active.id === 'cmd') return false;
    if (box && box.value.trim().length > 0) return false;
    return true;
  }}
  setInterval(function(){{ if (safeToRefresh()) location.reload(); }}, 5000);
}})();
</script>
</body></html>'''


def build_handler(state: ControlCenterState):
    from . import panel_auth as _panel_auth

    throttle = _panel_auth.LoginThrottle()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _send(self, status: int, body: bytes, content_type: str,
                  headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, message: str, location: str = "/",
                      headers: dict[str, str] | None = None) -> None:
            # Location başlığı 64 KB'ı aşamaz; uzun hata metinlerini kısalt.
            safe = message if len(message) <= 400 else message[:380] + "..."
            self.send_response(303)
            if location == "/":
                self.send_header("Location", "/?message=" + quote(safe))
            else:
                self.send_header("Location", location)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/owner/login", "/owner/logout"}:
                if parsed.path == "/owner/logout":
                    self._send(200, b"cikis yapildi", "text/html; charset=utf-8",
                               headers={"Set-Cookie": _panel_auth.logout_cookie()})
                    return
                query = parse_qs(parsed.query)
                nxt = query.get("next", ["/"])[0] or "/"
                setup = not _panel_auth.owner_configured(state.runtime_dir)
                body = _panel_auth.render_login(nxt, setup=setup).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/intelligence":
                from .intelligence import render_html, snapshot

                body = render_html(snapshot(state.runtime_dir)).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/outputs":
                body = render_outputs_page(
                    state.output_index(),
                    state.project_documents(),
                ).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/outputs/view":
                query = parse_qs(parsed.query)
                directory = query.get("dir", [""])[0]
                filename = query.get("file", [""])[0]
                if not directory or not filename:
                    raise ValueError("dir and file are required")
                document = resolve_output_file(
                    state.console.artifacts_root if state.console else ".",
                    directory,
                    filename,
                )
                body = render_document_page(filename, document).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/outputs/project":
                query = parse_qs(parsed.query)
                project_id = query.get("project", [""])[0]
                filename = query.get("file", [""])[0]
                if not project_id or not filename:
                    raise ValueError("project and file are required")
                document = state.resolve_project_document(project_id, filename)
                body = render_document_page(filename, document).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/systems":
                body = render_systems_page(state.systems_status()).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/panels":
                body = render_panels_page(state.panel_directory()).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/office":
                body = render_office(state.office_model()).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/agent-office":
                from .office_3d import render_html as _render_3d
                self._send(200, _render_3d().encode("utf-8"), "text/html; charset=utf-8")
                return
                from .office_floor import FLOOR_HTML
                self._send(200, FLOOR_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/conversations":
                from .commune import recent as _recent_conversations

                body = json.dumps(_recent_conversations(state.runtime_dir, 20),
                                  ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/talk":
                # This endpoint records an owner_talk event in the worker mind.
                # Never allow unauthenticated visitors or cross-site GETs to
                # forge instructions in a persistent memory.
                verdict = _panel_auth.require(
                    state.runtime_dir, self.headers.get("Cookie", ""),
                    "/action/command",
                )
                origin = self.headers.get("Origin")
                expected = {
                    f"http://127.0.0.1:{self.server.server_port}",
                    f"http://localhost:{self.server.server_port}",
                    f"http://[::1]:{self.server.server_port}",
                }
                if (not verdict["allowed"]
                        or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        or (origin is not None and origin not in expected)):
                    self._send(403, b'{"error":"owner session required"}',
                               "application/json; charset=utf-8")
                    return
                from .worker_mind import load as _load_mind
                from .worker_mind import save as _save_mind

                query = parse_qs(parsed.query)
                worker = (query.get("worker") or [""])[0].strip()
                message = (query.get("msg") or [""])[0].strip()[:500]
                if not worker:
                    self._send(400, b'{"error":"worker gerekli"}', "application/json; charset=utf-8")
                    return
                department = (query.get("dept") or [""])[0].strip()
                mind = _load_mind(state.runtime_dir, worker, department)
                model = dict(mind.self_model or {})
                strategy = model.get("strategy") or {}
                forecast = model.get("forecast") or {}
                mood = model.get("mood") or {}
                plan = model.get("plan") or []
                goal = model.get("goal") or "-"
                rate = round(mind.success_rate * 100)

                reply = (
                    f"Ben {worker} ({mind.department}). "
                    f"Şu anki hedefim: {goal}. "
                    f"Planım: {' → '.join(plan) if plan else 'henüz plan yok'}. "
                    f"Başarı oranım %{rate} ({len(mind.events)} olay), "
                    f"risk görüşüm: {forecast.get('risk', 'bilinmiyor')}, "
                    f"ruh halim: {mood.get('label', 'nötr')}. "
                    f"Stratejim: en iyi eylem '{strategy.get('best_action', '-')}', "
                    f"risk toleransı {strategy.get('risk_tolerance', '-')}. "
                )
                lowered = message.lower()
                if any(word in lowered for word in ("neden", "niye")):
                    reply += "Sebep: geçmiş olaylarıma ve kuyruk durumuna bakarak karar veriyorum."
                elif any(word in lowered for word in ("öner", "ne yap")):
                    reply += f"Önerim: {goal} hedefi için önce '{plan[0] if plan else 'durum analizi'}' adımını atmalıyım."
                elif message:
                    reply += "Mesajını not aldım; bir sonraki turda dikkate alacağım."

                mind.events.append({
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "kind": "owner_talk",
                    "detail": f"sahip: {message[:160]}",
                    "ok": True,
                })
                _save_mind(state.runtime_dir, mind)
                body = json.dumps({"worker": worker, "reply": reply}, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/agent-office":
                from .agent_office import snapshot as agent_snapshot
                body = json.dumps(agent_snapshot(state.runtime_dir), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/roster":
                # 3D ofis ad/rol yedeği; yalnız kimlik görünürlüğü.
                from .agent_office import roster_index
                body = json.dumps(roster_index(state.runtime_dir), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path.startswith("/api/worker-card/"):
                from . import worker_card
                wid = unquote(parsed.path[len("/api/worker-card/"):])
                if not wid or not worker_card.exists(state.runtime_dir, wid):
                    self._send(404, b'{"error":"worker not found"}', "application/json; charset=utf-8")
                    return
                body = json.dumps(worker_card.card(state.runtime_dir, wid),
                                  ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path.startswith("/worker/"):
                from . import worker_card
                wid = unquote(parsed.path[len("/worker/"):])
                if not wid or not worker_card.exists(state.runtime_dir, wid):
                    self._send(404, b"worker not found", "text/plain; charset=utf-8")
                    return
                body = worker_card.render_html(
                    worker_card.card(state.runtime_dir, wid)).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/office":
                body = json.dumps(state.office_model(), indent=2).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/status":
                # This endpoint is public monitoring, not an owner session.
                # Never disclose control or authorization tokens in JSON.
                public_state = dict(state.snapshot())
                public_state.pop("panel_token", None)
                body = json.dumps(public_state, indent=2).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/":
                message = parse_qs(parsed.query).get("message", [""])[0]
                body = render_dashboard(state.snapshot(), message).encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            expected_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}", f"[::1]:{self.server.server_port}"}
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if (host not in expected_hosts or
                (origin is not None and origin != "http://" + host) or
                self.headers.get("Sec-Fetch-Site") == "cross-site"):
                self._send(403, b"local same-origin request required", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    self._send(413, b"invalid form size", "text/plain; charset=utf-8")
                    return
                form = parse_qs(self.rfile.read(length).decode("utf-8"))

                # --- sahip oturumu: giriş / kurulum / çıkış ---
                if self.path in {"/owner/login", "/owner/setup"}:
                    client = self.client_address[0]
                    if throttle.blocked(client):
                        self._redirect("ERROR: çok fazla deneme; 5 dk bekleyin",
                                       "/owner/login")
                        return
                    username = form.get("username", ["harun"])[0]
                    password = form.get("password", [""])[0]
                    nxt = form.get("next", ["/"])[0] or "/"
                    if self.path == "/owner/setup":
                        if _panel_auth.owner_configured(state.runtime_dir):
                            self._redirect("ERROR: sahip zaten kurulu")
                            return
                        if password != form.get("confirm", [""])[0]:
                            self._redirect("ERROR: parola eşleşmiyor", "/owner/login")
                            return
                        from . import owner_auth as _owner_auth
                        _owner_auth.init_owner(state.runtime_dir, username, password)
                    try:
                        session = _panel_auth.login(state.runtime_dir, username, password)
                    except (PermissionError, ValueError) as exc:
                        throttle.record_failure(client)
                        self._redirect(f"ERROR: {exc}", "/owner/login")
                        return
                    throttle.reset(client)
                    self._redirect("giriş başarılı", nxt,
                                   headers={"Set-Cookie":
                                            _panel_auth.session_cookie(session["token"])})
                    return
                if self.path == "/owner/logout":
                    self._redirect("çıkış yapıldı", "/",
                                   headers={"Set-Cookie": _panel_auth.logout_cookie()})
                    return

                # --- ayrıcalıklı panel eylemleri geçerli sahip oturumu ister ---
                verdict = _panel_auth.require(state.runtime_dir,
                                              self.headers.get("Cookie", ""), self.path)
                if not verdict["allowed"]:
                    try:
                        from .owner_auth import audit as _audit
                        _audit(state.runtime_dir, "panel.denied", path=self.path,
                               reason=verdict["reason"], client=self.client_address[0])
                    except Exception:  # noqa: BLE001 - denetim akışı bozmaz
                        pass
                    location = "/owner/login?next=" + quote(self.path)
                    self._redirect("ERROR: sahip oturumu gerekli", location)
                    return

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
                elif self.path == "/action/loop-start":
                    msg = state.start_growth_loop()
                elif self.path == "/action/loop-stop":
                    msg = state.stop_growth_loop()
                elif self.path.startswith("/action/autonomy/"):
                    action = self.path.rsplit("/", 1)[-1]
                    # Oturum yukarıda doğrulandı; eski statik token yerine
                    # sunucunun kendi panel token'ı içeride kullanılır.
                    msg = state.autonomy_control(
                        action, state.panel_token, self.client_address[0]
                    )
                elif self.path == "/action/command":
                    command = form.get("command", [""])[0].strip()
                    if not command:
                        raise ValueError("command required")
                    msg = state.handle_command(command)
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
