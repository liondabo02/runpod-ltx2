"""Controlled autonomy: CEO prioritisation driven through the real executor.

Safety rules: no paid providers (max_usd must stay 0), one mission at a time,
hard limits per run, persistent dedupe so a restart never re-runs a mission,
pause/resume and kill-switch files, and no executor call while the queue is idle.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
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
        directive = None
        for _ in range(5):
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
        counts = self.mission_counts_today()
        if directive is not None and (
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
            # Kuyruk boş: executor veya model çağrısı yapılmaz.
            self.state.status = "idle"
            self.state.last_reason = "yönlendirme yok (boşta)"
            self._persist()
            return None

        key = self._key(directive.department_id, directive.objective)
        if self.already_executed(key):
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

        self.state.status = "running"
        self._persist()
        started = time.monotonic()
        attempts = 0
        result: ConsoleResult | None = None

        while attempts <= self.limits.max_retries:
            attempts += 1
            result = self.console.run_department_mission(spec, directive.objective)
            elapsed = time.monotonic() - started
            if result.status == "routed":
                break
            if elapsed > self.limits.max_seconds_per_mission:
                self.state.last_reason = "süre sınırı aşıldı"
                break

        elapsed = time.monotonic() - started
        mission_id = result.mission.mission_id if result and result.mission else ""

        if result is not None and result.status == "routed":
            self.state.executed += 1
            self.state.status = "idle"
            self.state.last_mission = mission_id
            self.state.last_reason = result.message[:200]
            self._record(key, mission_id, directive.department_id, "completed")
        else:
            self.state.failed += 1
            self.state.status = "blocked"
            self.state.last_reason = (
                result.message[:200] if result is not None else "sonuç yok"
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
