"""Controlled autonomy: CEO prioritisation driven through the real executor.

Safety rules: no paid providers (max_usd must stay 0), one mission at a time,
hard limits per run, persistent dedupe so a restart never re-runs a mission,
pause/resume and kill-switch files, and no executor call while the queue is idle.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from .holding_office import HoldingOffice
from .owner_console import ConsoleResult, OwnerConsole


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AutonomyLimits:
    max_missions: int = 2
    max_seconds_per_mission: float = 120.0
    max_retries: int = 1
    max_usd: float = 0.0
    max_concurrent: int = 1

    def __post_init__(self) -> None:
        if self.max_usd != 0:
            raise ValueError("otel: ücretli kullanım kapalı olmalı (max_usd=0)")
        if self.max_concurrent != 1:
            raise ValueError("aynı anda tek görev çalışabilir")


@dataclass
class AutonomyState:
    status: str = "idle"  # idle | running | paused | stopped | blocked
    executed: int = 0
    failed: int = 0
    skipped_duplicate: int = 0
    last_mission: str | None = None
    last_reason: str = ""
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "executed": self.executed,
            "failed": self.failed,
            "skipped_duplicate": self.skipped_duplicate,
            "last_mission": self.last_mission,
            "last_reason": self.last_reason,
            "updated_at": self.updated_at,
        }


class AutonomyRunner:
    def __init__(
        self,
        console: OwnerConsole,
        runtime_dir: str | Path,
        *,
        limits: AutonomyLimits | None = None,
    ) -> None:
        self.console = console
        self.runtime_dir = Path(runtime_dir)
        self.limits = limits or AutonomyLimits()
        self.dedupe_path = self.runtime_dir / "autonomy-executed.jsonl"
        self.state_path = self.runtime_dir / "autonomy-state.json"
        self.pause_path = self.runtime_dir / "autonomy.pause"
        self.stop_path = self.runtime_dir / "autonomy.stop"
        self.plan_path = self.runtime_dir / "auto-plan.json"
        self._active_idea: tuple[str, str] | None = None
        self._active_improvement: str | None = None
        self.office = HoldingOffice(console)
        self.state = AutonomyState()

    # ------------------------------------------------------------------ safety
    def _key(self, department_id: str, objective: str) -> str:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        digest = hashlib.sha256(
            f"{department_id}|{objective}|{day}".encode("utf-8")
        ).hexdigest()
        return digest[:24]

    def already_executed(self, key: str) -> bool:
        if not self.dedupe_path.exists():
            return False
        for line in self.dedupe_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("key") == key:
                    return True
            except json.JSONDecodeError:
                continue
        return False

    def _record(self, key: str, mission_id: str, department: str, status: str) -> None:
        self.dedupe_path.parent.mkdir(parents=True, exist_ok=True)
        with self.dedupe_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "key": key,
                        "mission_id": mission_id,
                        "department": department,
                        "status": status,
                        "at": _now(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _persist(self) -> None:
        self.state.updated_at = _now()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _blocked_reason(self) -> str | None:
        if self.stop_path.exists():
            return "kill-switch aktif"
        if self.pause_path.exists():
            return "duraklatıldı"
        return None

    # --------------------------------------------------------------- operations
    def _log_action(self, action: str, detail: str = "") -> None:
        path = self.runtime_dir / "autonomy-actions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"at": _now(), "action": action, "detail": detail[:300]},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def pause(self) -> None:
        self.pause_path.write_text(_now(), encoding="utf-8")
        self.state.status = "paused"
        self._log_action("pause")
        self._persist()

    def resume(self) -> None:
        self.pause_path.unlink(missing_ok=True)
        self.stop_path.unlink(missing_ok=True)
        self.state.status = "idle"
        self._log_action("resume")
        self._persist()

    def stop(self) -> None:
        self.stop_path.write_text(_now(), encoding="utf-8")
        self.state.status = "stopped"
        self._log_action("stop", "acil durdurma")
        self._persist()

    def persisted_state(self) -> dict[str, object]:
        """Read the durable autonomy record (the daemon writes it).

        A freshly constructed runner (panel, CLI) must show the real numbers
        instead of a zeroed in-memory state, otherwise the dashboard lies
        about whether the holding is actually working.
        """

        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def spend_record(self) -> dict[str, float]:
        """Real model spend from the executor ledger (never a hard-coded zero).

        The autonomous loop promises zero paid calls; that promise is only
        credible if it is measured. Reads ``model-spend.jsonl`` written by the
        LLM executor and reports today's calls/cost plus the lifetime total.
        """

        path = self.runtime_dir / "model-spend.jsonl"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        calls_today = 0
        usd_today = 0.0
        usd_total = 0.0
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return {
                "paid_calls": 0,
                "paid_usd_today": 0.0,
                "paid_usd_total": 0.0,
            }
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                usd = float(record.get("usd") or 0)
            except (TypeError, ValueError):
                usd = 0.0
            usd_total += usd
            if str(record.get("at", "")).startswith(today) and usd > 0:
                calls_today += 1
                usd_today += usd
        return {
            "paid_calls": calls_today,
            "paid_usd_today": round(usd_today, 6),
            "paid_usd_total": round(usd_total, 6),
        }

    def status(self) -> dict[str, object]:
        state = self.state.to_dict()
        persisted = self.persisted_state()
        for key in (
            "executed",
            "failed",
            "skipped_duplicate",
            "last_mission",
            "last_reason",
            "updated_at",
        ):
            if key in persisted and persisted[key] not in (None, ""):
                state[key] = persisted[key]
        return {
            **state,
            "limits": {
                "max_missions": self.limits.max_missions,
                "max_seconds_per_mission": self.limits.max_seconds_per_mission,
                "max_retries": self.limits.max_retries,
                "max_usd": self.limits.max_usd,
                "max_concurrent": self.limits.max_concurrent,
            },
            **self.spend_record(),
        }

    def executed_departments_today(self) -> set[str]:
        return set(self.mission_counts_today())

    def mission_counts_today(self) -> dict[str, int]:
        """Today's delivered missions per department (for fair rotation)."""

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        counts: dict[str, int] = {}
        if not self.dedupe_path.exists():
            return counts
        for line in self.dedupe_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(entry.get("at", "")).startswith(day):
                department = entry.get("department")
                if department:
                    key = str(department)
                    counts[key] = counts.get(key, 0) + 1
        return counts

    # ------------------------------------------------------------ model planning
    def recent_objectives(self, limit: int = 20) -> list[str]:
        """Most recent objective titles, newest first (from the dedupe ledger)."""

        if not self.dedupe_path.exists():
            return []
        titles: list[str] = []
        for line in self.dedupe_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            objective = str(entry.get("objective") or "").strip()
            if objective and objective not in titles:
                titles.append(objective)
        return titles[-limit:][::-1]

    def _department_map(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for status in self.office.assessment():
            spec = self.console.book.get(status.department_id)
            names[status.department_id] = spec.name if spec else status.department_id
        return names

    def _project_map(self) -> dict[str, list[str]]:
        projects: dict[str, list[str]] = {}
        if self.console.projects is None:
            return projects
        for department_id in self._department_map():
            linked = self.console.projects.for_department(department_id)
            projects[department_id] = [link.name for link in linked]
        return projects

    def _load_plan(self, day: str) -> list[dict] | None:
        """Today's plan, or None when it has not been generated yet.

        An existing but empty plan means "generated and exhausted": the loop
        must stay idle instead of asking the model again on every tick.
        """

        try:
            payload = json.loads(self.plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if str(payload.get("day") or "") != day:
            return None
        items = payload.get("objectives")
        return list(items) if isinstance(items, list) else None

    def _save_plan(self, day: str, items: list[dict]) -> None:
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.plan_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"day": day, "objectives": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.plan_path)

    def plan_directive(self, excluded: set[str] | None = None) -> "Directive | None":
        """Turn the model's plan for today into the next directive.

        The plan is generated once per UTC day and consumed item by item, so a
        restart never repeats a task and the loop keeps moving after the fixed
        growth cycle is exhausted. Any failure leaves the loop idle instead of
        blocking it.
        """

        from .holding_office import Directive
        from . import model_planner

        excluded = excluded or set()

        # Sahibin fikri her şeyden önce gelir: fikir kuyruğunda bekleyen görev
        # varsa plan/model çağrısından önce o alınır.
        try:
            from .ideas import claim_next

            claimed_idea = claim_next(self.runtime_dir)
        except Exception:  # noqa: BLE001 - fikir kuyruğu isteğe bağlı
            claimed_idea = None
        if claimed_idea is not None:
            idea, task = claimed_idea
            if idea.department_id not in excluded:
                self._active_idea = (idea.idea_id, str(task.get("task_id") or ""))
                return Directive(
                    kind="idea",
                    department_id=idea.department_id,
                    objective=str(task.get("title") or idea.text),
                    reason=f"fikir: {idea.text[:90]}",
                    priority=0,
                )

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        items = self._load_plan(day)
        if items is None:
            projects = self._project_map()
            # Yalnız gerçek projesi olan departmanlar önerilebilir; aksi hâlde
            # plan, işçisi olmayan bir göreve dönüşür.
            departments = {
                department: name
                for department, name in self._department_map().items()
                if projects.get(department)
            }
            try:
                items = model_planner.propose_objectives(
                    departments,
                    projects,
                    self.recent_objectives(),
                    limit=3,
                    agents=self._agent_capabilities(),
                )
            except Exception:  # noqa: BLE001 - planning is best effort
                items = []
            if not items:
                # Model yoksa/limitliyse (internetsiz dahil) projeyi tara:
                # somut gözlemlerden görev üret.
                items = self._heuristic_plan(departments, projects)
            self._save_plan(day, items)
            if not items:
                return None

        remaining: list[dict] = []
        chosen: dict | None = None
        projects = self._project_map()
        for item in items:
            department = str(item.get("department") or "")
            title = str(item.get("title") or "")
            if (
                chosen is None
                and department not in excluded
                and department
                and title
                and projects.get(department)
            ):
                if not self.already_executed(self._key(department, title)):
                    chosen = item
                    continue
            remaining.append(item)
        if chosen is None:
            self._save_plan(day, remaining)
            return None
        self._save_plan(day, remaining)
        return Directive(
            kind="model_plan",
            department_id=str(chosen["department"]),
            objective=str(chosen["title"]),
            reason=str(chosen.get("why") or "model planı"),
            priority=2,
        )

    # ------------------------------------------------------- delivery verdict
    def _changed_from_result(self, result: object) -> int | None:
        """File count the worker reported, or None when it said nothing."""

        mission = getattr(result, "mission", None)
        steps = getattr(mission, "steps", ()) or ()
        for step in steps:
            summary = str(getattr(step, "worker_summary", "") or "")
            match = re.search(r"(\d+)\s+dosya değişti", summary)
            if match:
                return int(match.group(1))
        return None

    def _project_root(self, department_id: str) -> Path | None:
        if self.console.projects is None:
            return None
        for link in self.console.projects.for_department(department_id):
            root = getattr(link, "work_path", None) or getattr(link, "path", None)
            if root:
                return Path(root)
        return None

    def _acceptance_passed(self, department_id: str) -> tuple[bool, str]:
        """Independent acceptance: the project's own offline gate must pass.

        A browser load is evidence the page opens, not that the feature works.
        Projects without a gate cannot claim a verified delivery.
        """

        root = self._project_root(department_id)
        if root is None:
            return False, "proje kökü yok"
        gate = root / "tools" / "check_offline.py"
        if not gate.is_file():
            return False, "kabul kapısı yok (tools/check_offline.py)"
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        try:
            completed = subprocess.run(
                [sys.executable, str(gate)],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"kabul kapısı çalıştırılamadı: {type(exc).__name__}"
        if completed.returncode != 0:
            tail = (completed.stdout or completed.stderr or "").strip().splitlines()
            return False, "kabul kapısı düştü: " + (tail[-1][:160] if tail else "çıktı yok")
        return True, "kabul kapısı geçti"

    def delivery_verdict(self, result: object, department_id: str) -> tuple[bool, str]:
        """A routed mission only counts when it changed files and passed acceptance."""

        changed = self._changed_from_result(result)
        if changed is None:
            return False, "işçi dosya değişikliği bildirmedi"
        if changed <= 0:
            return False, "teslimat yok: 0 dosya değişti"
        if os.environ.get("AHOS_REQUIRE_ACCEPTANCE", "1").strip().lower() in {"0", "false", "no"}:
            return True, f"{changed} dosya değişti (kabul kapısı devre dışı)"
        ok, detail = self._acceptance_passed(department_id)
        if not ok:
            return False, f"{changed} dosya değişti ama {detail}"
        return True, f"{changed} dosya değişti; {detail}"

    def _heuristic_plan(
        self, departments: dict[str, str], projects: dict[str, list[str]]
    ) -> list[dict]:
        """Model-free objective generation from the project tree itself."""

        from .heuristic_planner import scan

        recent = {item.casefold() for item in self.recent_objectives()}
        items: list[dict] = []
        for department_id in sorted(departments):
            root = self._project_root(department_id)
            if root is None:
                continue
            for title in scan(root):
                if title.casefold() in recent:
                    continue
                items.append(
                    {
                        "department": department_id,
                        "title": title,
                        "why": "proje taraması (model gerekmez)",
                    }
                )
                if len(items) >= 3:
                    return items
        return items

    def _ensure_acceptance_baseline(self, department_id: str) -> None:
        """Pin the project gate once so the first QA run is not blocked."""

        root = self._project_root(department_id)
        artifacts = getattr(self.console, "artifacts_root", None)
        if root is None or artifacts is None:
            return
        try:
            from .acceptance_bootstrap import ensure_baseline

            ensure_baseline(root, artifacts)
        except Exception:  # noqa: BLE001 - pinning is best effort
            pass

    def _self_improvement_directive(self, excluded: set[str]) -> "Directive | None":
        """Kalite kuyruğundaki ilk görevi yönlendirmeye çevir."""

        from .holding_office import Directive

        path = self.runtime_dir / "self-improvement.jsonl"
        done_path = self.runtime_dir / "self-improvement-done.jsonl"
        done: set[str] = set()
        if done_path.is_file():
            for line in done_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    done.add(str(json.loads(line).get("title") or ""))
                except json.JSONDecodeError:
                    continue
        if not path.is_file():
            return None
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                task = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = str(task.get("title") or "")
            department = str(task.get("department") or "software")
            if not title or title in done or department in excluded:
                continue
            self._active_improvement = (title, department)
            return Directive(
                kind="self_improvement",
                department_id=department,
                objective=title,
                reason=str(task.get("why") or "kalite bütçesi"),
                priority=0,
            )
        return None

    def _idea_directive(self, excluded: set[str]) -> "Directive | None":
        """The owner's idea outranks the CEO queue, the cycle and the planner."""

        from .holding_office import Directive

        try:
            from .ideas import claim_next

            claimed = claim_next(self.runtime_dir)
        except Exception:  # noqa: BLE001 - idea queue is optional
            claimed = None
        if claimed is None:
            return None
        idea, task = claimed
        if idea.department_id in excluded:
            return None
        self._active_idea = (idea.idea_id, str(task.get("task_id") or ""))
        return Directive(
            kind="idea",
            department_id=idea.department_id,
            objective=str(task.get("title") or idea.text),
            reason=f"fikir: {idea.text[:90]}",
            priority=0,
        )

    def _recover_queue(self) -> dict:
        """Reopen orphaned missions once when a claim keeps failing."""

        database = self.runtime_dir / "company-service.db"
        if not database.exists():
            return {}
        try:
            from .queue_recovery import recover_file

            return recover_file(database)
        except Exception:  # noqa: BLE001 - recovery is best effort
            return {}

    def _agent_capabilities(self) -> dict[str, list[str]]:
        """Departments and their managers, so the planner knows who can do what."""

        from .roster import build_roster

        agents: dict[str, list[str]] = {}
        try:
            roster = build_roster(self.runtime_dir)
        except Exception:  # noqa: BLE001 - roster is advisory
            return agents
        for card in roster.get("agents", []):
            kind = card.get("kind")
            agent_id = str(card.get("id") or "")
            if kind == "department":
                agents[agent_id] = list(card.get("capabilities") or ())
            elif kind == "worker" and agent_id.endswith("-manager"):
                agents[agent_id] = list(card.get("capabilities") or ())
        return agents

    def _retry_budget_path(self) -> Path:
        return self.runtime_dir / "autonomy-retries.json"

    def _is_blocked(self, spec, objective: str) -> bool:
        """Aynı hedef daha önce blocked kaldıysa tekrar denemeyelim."""

        queue = self.console.queue
        if queue is None:
            return False
        try:
            db = getattr(queue, "path", None) or getattr(queue, "_path", None)
            if db is None:
                return False
            import sqlite3

            con = sqlite3.connect(str(db))
            try:
                row = con.execute(
                    """SELECT status FROM missions
                       WHERE primary_department = ? AND lower(objective) = lower(?)
                       ORDER BY rowid DESC LIMIT 1""",
                    (spec.department_id, objective),
                ).fetchone()
            finally:
                con.close()
        except Exception:  # noqa: BLE001 - kuyruk şeması onların
            return False
        return bool(row) and str(row[0]) == "blocked"

    def _reopen_blocked(self, spec, objective: str, *, force: bool = False) -> bool:
        """Give a blocked mission one fresh attempt per day.

        The queue keeps a mission id in BLOCKED forever, so a fixed bug (a
        parser change, a transient model error) could never be re-verified with
        the same objective. One bounded retry per day keeps that possible
        without turning a permanent failure into an endless loop.
        """

        queue = getattr(self.console, "queue", None)
        if queue is None:
            return False
        try:
            # Görev kimliği yalnız nesne metninden türetilmiyor; kuyrukta bu
            # departman + hedef için engellenmiş satırı bul ve onu yeniden aç.
            with queue._connect() as conn:  # noqa: SLF001 - aynı paket
                rows = conn.execute(
                    """
                    SELECT mission_id, status FROM missions
                    WHERE primary_department = ? AND lower(objective) = lower(?)
                      AND status IN ('blocked', 'failed')
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (spec.department_id, objective),
                ).fetchall()
        except Exception:  # noqa: BLE001 - queue schema is theirs
            return False
        if not rows:
            return False
        mission_id = str(rows[0]["mission_id"])

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            retries = json.loads(self._retry_budget_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            retries = {}
        if str(retries.get("day") or "") != day:
            retries = {"day": day, "ids": []}
        ids = [str(item) for item in retries.get("ids", [])]
        if mission_id in ids and not force:
            return False
        ids.append(mission_id)
        retries["ids"] = ids[-200:]
        try:
            self._retry_budget_path().write_text(
                json.dumps(retries, ensure_ascii=False), encoding="utf-8"
            )
            queue.enqueue(
                mission_id=mission_id,
                objective=objective,
                primary_department=spec.department_id,
                max_attempts=2,
                replace_existing=True,
            )
        except Exception:  # noqa: BLE001 - retry is best effort
            return False
        return True

    def run_once(self) -> ConsoleResult | None:
        blocked = self._blocked_reason()
        if blocked:
            self.state.status = "paused" if "duraklat" in blocked else "stopped"
            self.state.last_reason = blocked
            self._persist()
            return None

        # Yalnızca gerçek yürütücüsü olan (projesi bağlı) departmanlar otonom
        # çalışabilir; aksi hâlde işçi "yürütücü bağlı değil" diyerek durur.
        # Burada yalnızca *kullanılamayan* departmanlar dışlanır; bir departman
        # bugün bir görev yaptı diye günün geri kalanında tamamen kapatılmaz.
        excluded: set[str] = set()
        directive = self._idea_directive(excluded)
        if directive is None:
            directive = self._self_improvement_directive(excluded)
        for _ in range(5 if directive is None else 0):
            candidate = self.office.next_directive(exclude_departments=excluded)
            if candidate is None:
                break
            projects = (
                self.console.projects.for_department(candidate.department_id)
                if self.console.projects is not None
                else ()
            )
            if projects:
                directive = candidate
                break
            excluded.add(candidate.department_id)

        # CEO aynı işi tekrar öneriyorsa ya da o departman bugün zaten çalıştıysa
        # döngü kilitlenmesin: sıradaki en az çalışan proje departmanına geç.
        # Sahibin fikri ve kalite görevi bu kurala tabi DEĞİLDİR; onlar kendi
        # dedupe anahtarlarıyla korunur.
        counts = self.mission_counts_today()
        kind = str(getattr(directive, "kind", "") or "")
        if directive is not None and kind not in {"idea", "self_improvement"} and (
            self.already_executed(self._key(directive.department_id, directive.objective))
            or counts.get(directive.department_id, 0) >= 1
        ):
            directive = None

        if directive is None:
            # CEO yeni iş üretmediyse, projesi bağlı bir departman için
            # döngüden sıradaki *henüz yapılmamış* gerçek teslimat görevini
            # seç. Aynı gün içinde dört farklı iş sırayla ilerleyebilir;
            # tamamlanan iş tekrar seçilmez (gün bazlı dedupe anahtarı).
            # Sıralama bugünkü görev sayısına göre: en az çalışan önce gelir,
            # böylece tek proje (ör. ai-platform) bütün döngüyü tekeline almaz.
            from .growth_loop import GROWTH_CYCLE
            from .holding_office import Directive

            candidates = sorted(
                self.office.assessment(),
                key=lambda status: (counts.get(status.department_id, 0), status.department_id),
            )
            for status in candidates:
                department_id = status.department_id
                if department_id in excluded or status.department_id == "holding":
                    continue
                projects = (
                    self.console.projects.for_department(department_id)
                    if self.console.projects is not None
                    else ()
                )
                if not projects:
                    continue
                spec = self.console.book.get(department_id)
                if spec is None:
                    continue
                for offset in range(len(GROWTH_CYCLE)):
                    index = (status.missions + offset) % len(GROWTH_CYCLE)
                    objective = f"{spec.name}: {GROWTH_CYCLE[index]}"
                    if self._is_blocked(spec, objective):
                        continue
                    if not self.already_executed(
                        self._key(department_id, objective)
                    ):
                        directive = Directive(
                            kind="project_advance",
                            department_id=department_id,
                            objective=objective,
                            reason="proje döngüsü",
                            priority=1,
                        )
                        break
                if directive is not None:
                    break

        if directive is None:
            # Sabit döngü tükendiyse modelden günün planını iste; bu, holdingin
            # "ne yapacağız?" sorusunu kendi kendine yanıtlamasıdır.
            directive = self.plan_directive(excluded)

        if directive is None:
            # Kuyruk boş: executor veya model çağrısı yapılmaz.
            self.state.status = "idle"
            self.state.last_reason = "yönlendirme yok (boşta)"
            self._persist()
            return None

        key = self._key(directive.department_id, directive.objective)
        # Fikir ve kalite görevi kendi "bitti" kayıtlarıyla korunur; günlük
        # dedupe anahtarı onları kalıcı olarak engellememeli.
        if self.already_executed(key) and kind not in {"idea", "self_improvement"}:
            self.state.skipped_duplicate += 1
            self.state.last_reason = f"tekrar engellendi: {key}"
            self._persist()
            return None

        spec = self.console.book.get(directive.department_id)
        if spec is None:
            self.state.status = "blocked"
            self.state.last_reason = f"bilinmeyen departman: {directive.department_id}"
            self._persist()
            return None

        if self._project_root(directive.department_id) is None:
            # Kod projesi olmayan şirket: iş, iş belgesi olarak teslim edilir.
            from .company_foundry import found
            from .owner_console import CommandKind

            company = found(
                self.console.book,
                self.console.book.workforce(),
                self.runtime_dir,
                directive.objective,
                spec=spec,
            )
            delivered = company.validated
            if delivered:
                self.state.executed += 1
                self.state.status = "idle"
            else:
                self.state.failed += 1
                self.state.status = "blocked"
            self.state.last_reason = company.summary[:200]
            self._record(
                key,
                f"DOC-{company.company_id}",
                directive.department_id,
                "completed" if delivered else "failed",
            )
            self._persist()
            return ConsoleResult(
                kind=CommandKind.TASK,
                status="routed" if delivered else "blocked",
                message=f"{company.summary} · teslimat: {company.deliverable}",
                department_id=company.company_id,
            )

        self.state.status = "running"
        self._persist()
        started = time.monotonic()
        attempts = 0
        result: ConsoleResult | None = None

        self._reopen_blocked(
            spec,
            directive.objective,
            force=kind in {"idea", "self_improvement"},
        )
        self._ensure_acceptance_baseline(directive.department_id)

        while attempts <= self.limits.max_retries:
            attempts += 1
            stop_reason = self._blocked_reason()
            if stop_reason:
                # Acil durdurma/duraklatma görev ortasında da geçerli: yeni
                # deneme başlatılmaz.
                self.state.status = "stopped"
                self.state.last_reason = f"iptal: {stop_reason}"
                self._record(key, "", directive.department_id, "cancelled")
                self._persist()
                return None
            result = self.console.run_department_mission(spec, directive.objective)
            elapsed = time.monotonic() - started
            if result.status == "routed":
                break
            if elapsed > self.limits.max_seconds_per_mission:
                self.state.last_reason = "süre sınırı aşıldı"
                break

        elapsed = time.monotonic() - started
        mission_id = result.mission.mission_id if result and result.mission else ""

        if (
            result is not None
            and result.status == "routed"
            and "zaten tamamlanmış" in (result.message or "")
        ):
            # Kuyruk bu görevi daha önce bitirmiş: teslimat sayma, kanıt
            # serisini de bozma; sadece tekrar denemeyi engelle.
            self.state.skipped_duplicate += 1
            self.state.status = "idle"
            self.state.last_reason = "zaten tamamlanmış görev atlandı"
            self._record(key, mission_id, directive.department_id, "skipped")
            self._persist()
            return None

        if result is not None and result.status == "routed":
            if self._active_idea is not None:
                try:
                    from .ideas import complete

                    complete(
                        self._active_idea[0],
                        self._active_idea[1],
                        self.runtime_dir,
                        success=True,
                    )
                except Exception:  # noqa: BLE001 - fikir kaydı isteğe bağlı
                    pass
                self._active_idea = None
            delivered, verdict = self.delivery_verdict(result, directive.department_id)
            if not delivered:
                # Sıfır dosya ya da doğrulanmamış kabul: başarı sayılmaz.
                self.state.failed += 1
                self.state.status = "blocked"
                self.state.last_reason = verdict[:200]
                self._record(key, mission_id, directive.department_id, "failed")
                self._persist()
                # A routed command is not a successful delivery when the
                # independent file/evidence gate rejected it. Return the
                # authoritative outcome to the daemon and all downstream
                # consumers instead of leaking status="routed".
                return replace(
                    result,
                    status="blocked",
                    message=f"teslimat kanıtı başarısız: {verdict[:180]}",
                )
            self.state.executed += 1
            self.state.status = "idle"
            self.state.last_mission = mission_id
            self.state.last_reason = result.message[:200]
            self._record(key, mission_id, directive.department_id, "completed")
            if self._active_improvement is not None:
                improvement_title, improvement_department = self._active_improvement
                # Yalnız gerçekten o departmanın görevi tamamlandıysa "bitti" yaz.
                if (
                    directive.department_id == improvement_department
                    and directive.objective == improvement_title
                ):
                    record = {
                        "at": _now(),
                        "title": improvement_title,
                        "mission_id": mission_id,
                    }
                    try:
                        with (self.runtime_dir / "self-improvement-done.jsonl").open(
                            "a", encoding="utf-8"
                        ) as handle:
                            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    except OSError:  # pragma: no cover - best effort
                        pass
                self._active_improvement = None
        else:
            if self._active_idea is not None:
                try:
                    from .ideas import complete

                    complete(
                        self._active_idea[0],
                        self._active_idea[1],
                        self.runtime_dir,
                        success=False,
                    )
                except Exception:  # noqa: BLE001
                    pass
                self._active_idea = None
            self.state.failed += 1
            self.state.status = "blocked"
            self.state.last_reason = (
                result.message[:200] if result is not None else "sonuç yok"
            )
            if "sahiplenilemedi" in self.state.last_reason:
                # Kuyrukta sahipsiz kalmış satır olabilir; bir kez kurtarmayı dene.
                recovery = self._recover_queue()
                if recovery:
                    self.state.last_reason += (
                        f" · kurtarma: {recovery.get('reopened_stuck', 0)} yeniden açıldı"
                    )
            self._record(key, mission_id, directive.department_id, "failed")

        if self.state.executed >= self.limits.max_missions:
            self.state.status = "stopped"
            self.state.last_reason = "görev limiti doldu"

        self._persist()
        return result

    def run(self, *, ticks: int = 2) -> list[ConsoleResult | None]:
        results: list[ConsoleResult | None] = []
        for _ in range(max(1, min(ticks, self.limits.max_missions))):
            if self.state.status in {"stopped", "paused"}:
                break
            results.append(self.run_once())
        return results
