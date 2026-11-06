from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .autonomous_company import QueuedMission
from .departments import (
    CapabilitySpec,
    DepartmentBook,
    DepartmentSpec,
    WorkerSpec,
    utc_now,
)

if TYPE_CHECKING:  # pragma: no cover
    from .owner_console import ConsoleResult, OwnerConsole

HOLDING_DEPARTMENT_ID = "holding"
SECURITY_DEPARTMENT_ID = "guvenlik"
AI_PLATFORM_DEPARTMENT_ID = "ai-platform"

_PROJECT_STALE_HOURS = 24


def _parse(value: object) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _tool(
    *,
    worker_id: str,
    name: str,
    role: str,
    team_id: str,
    capabilities: tuple[str, ...],
    reports_to: str | None,
    authority: str = "B",
) -> WorkerSpec:
    return WorkerSpec(
        worker_id=worker_id,
        name=name,
        role=role,
        team_id=team_id,
        capabilities=frozenset(capabilities),
        reports_to=reports_to,
        authority_level=authority,
    )


def holding_department_spec() -> DepartmentSpec:
    """The CEO office that sits above every department manager."""

    capabilities = (
        CapabilitySpec("holding.portfolio_management", "Departman portföyünü yönetir."),
        CapabilitySpec("holding.escalation", "Tıkanan işleri çözer."),
        CapabilitySpec("holding.budget_approval", "Bütçe ve maliyet kararlarını verir."),
        CapabilitySpec("holding.roadmap", "Holding yol haritasını belirler."),
    )
    workers = (
        _tool(
            worker_id="ceo-01",
            name="CEO",
            role="department_manager",
            team_id="holding-executive",
            capabilities=(
                "planning",
                "task_decomposition",
                "routing",
                "portfolio_management",
                "escalation",
                "budget_approval",
                "roadmap",
            ),
            reports_to=None,
            authority="A",
        ),
        _tool(
            worker_id="ceo-chief-of-staff-01",
            name="Genel Koordinatör",
            role="operations_specialist",
            team_id="holding-executive",
            capabilities=("coordination", "reporting", "scheduling", "roadmap"),
            reports_to="ceo-01",
            authority="A",
        ),
    )
    return DepartmentSpec(
        department_id=HOLDING_DEPARTMENT_ID,
        name="Holding Yönetimi (CEO)",
        mission=(
            "Departman müdürlerini yönetir, öncelikleri belirler, tıkanıklıkları "
            "açar ve holdingin bütününü sahibine karşı temsil eder."
        ),
        capabilities=capabilities,
        workers=workers,
        keywords=("holding", "ceo", "yonetim", "portfoy", "holding yonetimi"),
        source="holding",
    )


def security_department_spec() -> DepartmentSpec:
    """Continuous GitHub / repository guardian department."""

    keywords = (
        "guvenlik",
        "github",
        "bagimlilik",
        "secret",
        "sizinti",
        "audit",
        "koruma",
        "dependency",
    )
    suffix = " Owner keywords: " + " ".join(keywords) + "."
    capabilities = (
        CapabilitySpec(
            "guvenlik.repo_audit",
            "Depo durumu, dal, kirli çalışma ağacı ve büyük dosya denetimi." + suffix,
        ),
        CapabilitySpec(
            "guvenlik.dependency_audit",
            "Bağımlılık sabitleme ve güncellik denetimi." + suffix,
        ),
        CapabilitySpec(
            "guvenlik.secret_scan",
            "Depoya sızabilecek anahtar ve gizli dosya taraması." + suffix,
        ),
        CapabilitySpec(
            "guvenlik.release_audit",
            "Sürüm, CI ve yedek dosya denetimi." + suffix,
        ),
    )
    workers = (
        _tool(
            worker_id="guvenlik-manager",
            name="Koruma Müdürü",
            role="department_manager",
            team_id="guvenlik-leadership",
            capabilities=(
                "planning",
                "task_decomposition",
                "routing",
                "repo_audit",
                "dependency_audit",
                "secret_scan",
                "release_audit",
            ),
            reports_to=None,
            authority="A",
        ),
        _tool(
            worker_id="guvenlik-repo-guardian",
            name="Depo Bekçisi",
            role="devops_engineer",
            team_id="guvenlik-audit",
            capabilities=("repo_audit", "release_audit"),
            reports_to="guvenlik-manager",
        ),
        _tool(
            worker_id="guvenlik-dependency-auditor",
            name="Bağımlılık Denetçisi",
            role="data_analyst",
            team_id="guvenlik-audit",
            capabilities=("dependency_audit",),
            reports_to="guvenlik-manager",
        ),
        _tool(
            worker_id="guvenlik-secret-scanner",
            name="Gizli Anahtar Tarayıcısı",
            role="qa_engineer",
            team_id="guvenlik-audit",
            capabilities=("secret_scan",),
            reports_to="guvenlik-manager",
        ),
        _tool(
            worker_id="guvenlik-release-guardian",
            name="Sürüm Bekçisi",
            role="operations_specialist",
            team_id="guvenlik-release",
            capabilities=("release_audit", "reporting"),
            reports_to="guvenlik-manager",
        ),
    )
    return DepartmentSpec(
        department_id=SECURITY_DEPARTMENT_ID,
        name="Güvenlik ve Kaynak Koruma Departmanı",
        mission=(
            "Sistemin kaynak kodunu, bağımlılıklarını ve sırlarını sürekli izler; "
            "GitHub tarafındaki riskleri ve iyileştirme fırsatlarını raporlar."
        ),
        capabilities=capabilities,
        workers=workers,
        keywords=keywords,
        source="holding",
    )


def ai_platform_department_spec() -> DepartmentSpec:
    """Yapay zekâ platformu: araç kataloğu, model geçidi ve değerlendirme."""

    keywords = (
        "harun",
        "foundry",
        "ai platform",
        "yapay zeka",
        "model",
        "katalog",
        "tool catalog",
        "litellm",
    )
    suffix = " Owner keywords: " + " ".join(keywords) + "."
    capabilities = (
        CapabilitySpec("ai-platform.tool_curation", "Araç kataloğu ve lisans denetimi." + suffix),
        CapabilitySpec("ai-platform.model_gateway", "Model geçidi ve maliyet kontrolü." + suffix),
        CapabilitySpec("ai-platform.evaluation", "Model ve araç değerlendirmesi." + suffix),
        CapabilitySpec("ai-platform.integration", "Harici AI platformlarının entegrasyonu." + suffix),
    )
    workers = (
        _tool(
            worker_id="ai-platform-manager",
            name="AI Platform Müdürü",
            role="department_manager",
            team_id="ai-platform-leadership",
            capabilities=(
                "planning",
                "task_decomposition",
                "routing",
                "tool_curation",
                "model_gateway",
                "evaluation",
                "integration",
            ),
            reports_to=None,
            authority="A",
        ),
        _tool(
            worker_id="ai-platform-tool-curator",
            name="Araç Küratörü",
            role="researcher",
            team_id="ai-platform-tools",
            capabilities=("tool_curation", "integration"),
            reports_to="ai-platform-manager",
        ),
        _tool(
            worker_id="ai-platform-gateway-engineer",
            name="Model Geçidi Mühendisi",
            role="software_engineer",
            team_id="ai-platform-tools",
            capabilities=("model_gateway", "integration"),
            reports_to="ai-platform-manager",
        ),
        _tool(
            worker_id="ai-platform-evaluator",
            name="Değerlendirme Uzmanı",
            role="data_analyst",
            team_id="ai-platform-eval",
            capabilities=("evaluation",),
            reports_to="ai-platform-manager",
        ),
    )
    return DepartmentSpec(
        department_id=AI_PLATFORM_DEPARTMENT_ID,
        name="Yapay Zekâ Platformu",
        mission=(
            "Holdingin yapay zekâ altyapısını yönetir: araç kataloğu, model "
            "geçidi, maliyet kontrolü ve dış platform entegrasyonları."
        ),
        capabilities=capabilities,
        workers=workers,
        keywords=keywords,
        source="holding",
    )


def ensure_builtin_departments(book: DepartmentBook) -> tuple[DepartmentSpec, ...]:
    """Create or refresh the CEO office, guardian and AI platform departments."""

    created: list[DepartmentSpec] = []
    for factory in (
        holding_department_spec,
        security_department_spec,
        ai_platform_department_spec,
    ):
        spec = factory()
        existing = book.get(spec.department_id)
        if existing is None or existing.source == "holding":
            created.append(book.add(spec, replace=True))
    return tuple(created)


@dataclass(frozen=True, slots=True)
class DepartmentStatus:
    department_id: str
    name: str
    workers: int
    missions: int
    blocked: int
    last_activity: str | None
    project_count: int


@dataclass(frozen=True, slots=True)
class Directive:
    kind: str
    department_id: str
    objective: str
    reason: str
    priority: int


class HoldingOffice:
    """CEO layer: reads the whole holding and issues one directive at a time."""

    def __init__(self, console: "OwnerConsole") -> None:
        self.console = console

    # ------------------------------------------------------------------ reading
    def _missions(self) -> tuple[QueuedMission, ...]:
        queue = self.console.queue
        if queue is None:
            return ()
        try:
            return tuple(queue.list()[-500:])
        except Exception:  # pragma: no cover - defensive
            return ()

    def assessment(self) -> tuple[DepartmentStatus, ...]:
        missions = self._missions()
        projects = self.console.projects
        statuses: list[DepartmentStatus] = []

        for spec in self.console.book.active():
            department_missions = [
                mission
                for mission in missions
                if mission.primary_department == spec.department_id
            ]
            blocked = sum(
                1 for mission in department_missions if mission.status.value == "blocked"
            )
            last = max(
                (mission.updated_at for mission in department_missions),
                default=None,
            )
            project_count = (
                len(projects.for_department(spec.department_id))
                if projects is not None
                else 0
            )
            statuses.append(
                DepartmentStatus(
                    department_id=spec.department_id,
                    name=spec.name,
                    workers=len(spec.workers),
                    missions=len(department_missions),
                    blocked=blocked,
                    last_activity=last,
                    project_count=project_count,
                )
            )
        return tuple(statuses)

    def next_directive(
        self,
        *,
        now: datetime | None = None,
        exclude_departments: set[str] | None = None,
    ) -> Directive | None:
        moment = now or datetime.now(timezone.utc)
        skipped = set(exclude_departments or ())
        statuses = [
            status
            for status in self.assessment()
            if status.department_id != HOLDING_DEPARTMENT_ID
            and status.department_id not in skipped
        ]
        if not statuses:
            return None

        blocked = [status for status in statuses if status.blocked]
        if blocked:
            target = sorted(blocked, key=lambda s: (-s.blocked, s.department_id))[0]
            return Directive(
                kind="unblock",
                department_id=target.department_id,
                objective=(
                    f"{target.name}: engellenen {target.blocked} görevi incele, "
                    "nedenini raporla ve çözüm planı çıkar."
                ),
                reason=f"{target.blocked} engellenmiş görev var",
                priority=3,
            )

        stale_window = timedelta(hours=_PROJECT_STALE_HOURS)
        stale_projects = [
            status
            for status in statuses
            if status.project_count
            and (
                status.last_activity is None
                or (
                    (moment - _parse(status.last_activity)) > stale_window
                    if _parse(status.last_activity)
                    else True
                )
            )
        ]
        if stale_projects:
            target = sorted(stale_projects, key=lambda s: s.department_id)[0]
            return Directive(
                kind="project_advance",
                department_id=target.department_id,
                objective=(
                    f"{target.name}: bağlı projede {_PROJECT_STALE_HOURS} saattir "
                    "ilerleme yok; entegrasyon planının sıradaki adımını çalıştır."
                ),
                reason="bağlı proje ilerlemiyor",
                priority=2,
            )

        target = sorted(statuses, key=lambda s: (s.missions, s.department_id))[0]
        if target.missions > 0 and all(status.missions > 0 for status in statuses):
            return None
        return Directive(
            kind="grow",
            department_id=target.department_id,
            objective=(
                f"{target.name}: haftalık gelişim planını güncelle ve ilk işi tanımla."
            ),
            reason="en az görev alan departman",
            priority=1,
        )

    # ---------------------------------------------------------------- reporting
    def brief(self, *, now: datetime | None = None) -> str:
        statuses = self.assessment()
        managed = [s for s in statuses if s.department_id != HOLDING_DEPARTMENT_ID]
        total_workers = sum(s.workers for s in statuses)
        total_projects = sum(s.project_count for s in statuses)
        blocked = sum(s.blocked for s in statuses)
        directive = self.next_directive(now=now)

        lines = [
            "Holding durumu (CEO özeti)",
            f"- Departman: {len(managed)} · ajan: {total_workers} · "
            f"bağlı proje: {total_projects} · engel: {blocked}",
        ]
        ranking = sorted(managed, key=lambda s: (-s.missions, s.department_id))
        for status in ranking[:8]:
            project_note = f", {status.project_count} proje" if status.project_count else ""
            lines.append(
                f"- {status.name} (`{status.department_id}`): "
                f"{status.workers} ajan, {status.missions} görev{project_note}"
            )
        if directive is None:
            lines.append("Karar: holding dengede — yeni yönlendirme gerekmiyor.")
        else:
            lines.append(
                f"Karar: `{directive.department_id}` → {directive.objective} "
                f"(neden: {directive.reason})"
            )
        return "\n".join(lines)

    # ---------------------------------------------------------------- execution
    def execute(self, directive: Directive) -> "ConsoleResult":
        spec = self.console.book.get(directive.department_id)
        if spec is None:
            raise KeyError(f"unknown department: {directive.department_id}")
        return self.console.run_department_mission(spec, directive.objective)

    def run_once(self) -> "ConsoleResult | None":
        directive = self.next_directive()
        if directive is None:
            return None
        return self.execute(directive)

    def managers(self) -> tuple[tuple[str, str, str], ...]:
        """(department_id, department_name, manager worker_id) for the brief."""

        result = []
        for spec in self.console.book.active():
            result.append((spec.department_id, spec.name, spec.manager.worker_id))
        return tuple(result)

    def status(self) -> dict[str, object]:
        directive = self.next_directive()
        return {
            "generated_at": utc_now(),
            "departments": len(self.assessment()),
            "next_directive": (
                None
                if directive is None
                else {
                    "kind": directive.kind,
                    "department_id": directive.department_id,
                    "objective": directive.objective,
                    "reason": directive.reason,
                    "priority": directive.priority,
                }
            ),
        }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    from .owner_console import build_default_console

    parser = argparse.ArgumentParser(
        prog="ahos-ceo",
        description="Holding CEO özeti ve öncelik yönlendirmesi.",
    )
    parser.add_argument(
        "--runtime-dir",
        default=str(Path(__file__).resolve().parents[1] / "runtime"),
    )
    parser.add_argument("--run", action="store_true", help="sıradaki yönlendirmeyi çalıştır")
    args = parser.parse_args(argv)

    console = build_default_console(args.runtime_dir)
    office = HoldingOffice(console)
    print(office.brief())

    if args.run:
        result = office.run_once()
        print()
        print(result.message if result is not None else "yönlendirme yok")
    return 0
