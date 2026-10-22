from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .departments import (
    DepartmentBook,
    DepartmentSpec,
    ascii_fold,
    slugify,
)
from .autonomous_company import PersistentMissionQueue, QueueStatus
from .mission_orchestrator import (
    MissionResult,
    MissionStepSpec,
    MissionStatus,
    MultiWorkerMissionOrchestrator,
)
from .org_synthesis import next_available_id, synthesize_department
from .code_work import make_project_executor
from .llm_executor import load_settings, make_model_executor
from .github_guardian import (
    default_repo_root,
    make_guardian_executor,
)
from .holding_office import (
    SECURITY_DEPARTMENT_ID,
    ensure_builtin_departments,
)
from .projects import (
    ProjectLink,
    ProjectRegistry,
    audit_project,
    build_integration_plan,
    detect_project_kind,
    import_project,
    project_id_for,
    render_audit,
    resolve_project_source,
)
from .registry import DepartmentCapabilityRegistry, department_key
from .routing import DepartmentRoutingEngine
from .virtual_workforce import WorkerProfile
from .worker_runtime import (
    QaExecutor,
    WorkerExecutionResult,
    WorkerExecutor,
    local_pass_qa,
)
from .workforce_execution import WorkItem

ROUTING_THRESHOLD = 15
_FOUNDING_OBJECTIVE = (
    "Departman kuruluşu: misyonu netleştir, ekip yapısını doğrula ve ilk 30 gün "
    "planını üret."
)


class OwnerCommandError(RuntimeError):
    """The owner command could not be understood or executed."""


class CommandKind(str, Enum):
    CREATE_DEPARTMENT = "create_department"
    ATTACH_PROJECT = "attach_project"
    TASK = "task"
    STATUS = "status"
    HELP = "help"


_CREATE_VERBS = (
    "kur",
    "kurul",
    "kural",
    "olustur",
    "ac",
    "baslat",
    "insa",
    "hayata",
    "create",
    "build",
    "found",
    "launch",
    "start",
    "setup",
    "establish",
    "make",
)

# Türkçe çekimler için önek eşleşmesi güvenli; İngilizce fiiller tam eşleşmeli
# (ör. "foundry" kelimesi "found" fiili sayılmamalı).
_CREATE_PREFIXES = ("kur", "olustur", "baslat", "insa")
_CREATE_EXACT = frozenset(
    {
        "kur",
        "olustur",
        "ac",
        "baslat",
        "insa",
        "create",
        "build",
        "found",
        "launch",
        "start",
        "setup",
        "establish",
        "make",
    }
)

_DEPARTMENT_NOUNS = (
    "departman",
    "sirket",
    "studio",
    "stüdyo",
    "studyo",
    "bolum",
    "birim",
    "ekip",
    "ekib",
    "kadro",
    "unit",
    "division",
    "company",
    "department",
    "team",
    "agency",
    "ajans",
    "sirketi",
)

_STATUS_WORDS = (
    "durum",
    "rapor",
    "status",
    "report",
    "ozet",
    "summary",
    "neler var",
    "what do we have",
)

_HELP_WORDS = ("yardim", "help", "nasil kullanilir", "komutlar")

_BIND_VERBS = (
    "bagla",
    "baglant",
    "bagli",
    "iliskilendir",
    "ata",
    "ekle",
    "link",
    "attach",
)

_PROJECT_NOUNS = ("proje", "project", "uygulama", "repo")


@dataclass(frozen=True, slots=True)
class OwnerCommand:
    kind: CommandKind
    text: str
    domain_text: str = ""


@dataclass(frozen=True, slots=True)
class ConsoleResult:
    kind: CommandKind
    status: str
    message: str
    department_id: str | None = None
    mission: MissionResult | None = None

    @property
    def ok(self) -> bool:
        return self.status in {
            "department_created",
            "project_linked",
            "routed",
            "status_report",
            "help",
        }


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", ascii_fold(text))


def _matches_any(token: str, prefixes: Iterable[str]) -> bool:
    return any(token == prefix or token.startswith(prefix) for prefix in prefixes)


def _is_create_verb(token: str) -> bool:
    if token in _CREATE_EXACT:
        return True
    # Türkçe çekimler: "kuruyoruz", "oluşturalım", "başlatıldı"...
    return any(
        token.startswith(prefix) and token != prefix
        for prefix in _CREATE_PREFIXES
    )


def parse_owner_command(text: str) -> OwnerCommand:
    """Deterministic TR/EN intent parser; never calls a model."""

    cleaned = text.strip()
    if not cleaned:
        raise OwnerCommandError("komut boş olamaz")

    folded = ascii_fold(cleaned)
    tokens = _tokens(cleaned)

    if len(tokens) <= 4 and any(word in folded for word in _HELP_WORDS):
        return OwnerCommand(kind=CommandKind.HELP, text=cleaned)

    if len(tokens) <= 4 and any(word in folded for word in _STATUS_WORDS):
        return OwnerCommand(kind=CommandKind.STATUS, text=cleaned)

    has_create_verb = any(_is_create_verb(token) for token in tokens)
    has_department_noun = any(
        _matches_any(token, _DEPARTMENT_NOUNS) for token in tokens
    )
    has_bind_verb = any(_matches_any(token, _BIND_VERBS) for token in tokens)
    has_project_noun = any(
        _matches_any(token, _PROJECT_NOUNS) for token in tokens
    )

    # Proje bağlama, "kur" gibi fiiller geçse bile önceliklidir:
    # "harun-ai-foundry projesini ... bağla" yanlışlıkla departman kurmasın.
    if has_project_noun and has_bind_verb:
        return OwnerCommand(
            kind=CommandKind.ATTACH_PROJECT,
            text=cleaned,
            domain_text=cleaned,
        )

    if has_create_verb and has_department_noun:
        return OwnerCommand(
            kind=CommandKind.CREATE_DEPARTMENT,
            text=cleaned,
            domain_text=cleaned,
        )

    return OwnerCommand(kind=CommandKind.TASK, text=cleaned, domain_text=cleaned)


class DepartmentStepPlanner:
    """Deterministic manager planner: brief -> produce -> review.

    It replaces an LLM planner so the owner console can run a real mission with
    zero tokens. Every step's required capabilities are taken from workers that
    actually exist in the department.
    """

    def __init__(self, spec: DepartmentSpec) -> None:
        self.spec = spec
        self.delivery_worker = self._pick_delivery_worker()
        self.quality_department = "quality"

    def _pick_delivery_worker(self) -> WorkerProfile:
        candidates = [
            worker
            for worker in self.spec.workers
            if not worker.is_manager and "quality" not in worker.team_id
        ]
        if not candidates:
            candidates = [worker for worker in self.spec.workers if not worker.is_manager]
        candidates.sort(key=lambda worker: (-len(worker.capabilities), worker.worker_id))
        return candidates[0].to_worker_profile(self.spec.department_id)

    def __call__(
        self,
        mission_id: str,
        objective: str,
        manager_id: str,
    ) -> tuple[MissionStepSpec, ...]:
        manager = next(
            worker
            for worker in self.spec.workers
            if worker.worker_id == manager_id
        )
        planning_capability = (
            "planning" if "planning" in manager.capabilities else sorted(manager.capabilities)[0]
        )

        return (
            MissionStepSpec(
                step_id="brief",
                title=f"{self.spec.name} — görevi analiz et: {objective}",
                department=self.spec.department_id,
                required_capabilities=frozenset({planning_capability}),
            ),
            MissionStepSpec(
                step_id="produce",
                title=f"{self.spec.name} — üretim: {objective}",
                department=self.spec.department_id,
                required_capabilities=frozenset(self.delivery_worker.capabilities),
                depends_on=("brief",),
            ),
            MissionStepSpec(
                step_id="review",
                title=f"{self.spec.name} — kalite kontrolü: {objective}",
                department=self.quality_department,
                required_capabilities=frozenset({"verification"}),
                depends_on=("produce",),
            ),
        )


def make_artifact_executor(artifacts_root: str | Path) -> WorkerExecutor:
    """Zero-cost executor that writes a markdown deliverable per work item."""

    root = Path(artifacts_root)

    def _execute(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", item.task_id).strip("._") or "task"
        destination = root / safe_task
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / "deliverable.md"

        body = (
            f"# {item.title}\n\n"
            f"- Gorev: {item.task_id}\n"
            f"- Departman: {item.department}\n"
            f"- Isci: {worker_id}\n"
            f"- Yetkinlikler: {', '.join(sorted(item.required_capabilities))}\n\n"
            "## Sonuc\n\n"
            "Bu kayıt yalnız görev metadatasıdır. Üretim yürütücüsü bağlı değil; "
            "gerçek üretim tamamlanmadı.\n"
        )
        path.write_text(body, encoding="utf-8")

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=item.task_id.rsplit(":", 1)[-1] != "produce",
            summary=(
                ("Üretim yürütücüsü bağlı değil; görev tamamlanmadı. " if item.task_id.rsplit(":", 1)[-1] == "produce" else "") + f"{item.department}/"
                f"{item.task_id.rsplit(':', 1)[-1]} metadata kaydı oluşturuldu "
                f"({worker_id}); çıktı: {path.name}"
            ),
            artifacts=(str(path),),
        )

    return _execute


_PROJECT_NAME_PATTERN = re.compile(
    r"([A-Za-zÇĞİÖŞÜçğıöşü0-9_.-]{2,40})\s+proje\w*",
    re.IGNORECASE,
)


def _project_name_from_text(text: str) -> str:
    match = _PROJECT_NAME_PATTERN.search(text)
    if match:
        candidate = match.group(1).strip(" .-_")
        if candidate and candidate.lower() not in {"bir", "bu", "mevcut", "yeni"}:
            return candidate

    for token in re.findall(r"[A-Za-zÇĞİŞÖÜçğıöşü0-9_.-]{2,40}", text):
        if ascii_fold(token).lower() not in {
            "proje",
            "projesini",
            "projesi",
            "bagla",
            "departman",
            "departmanina",
            "bir",
            "bu",
        }:
            return token
    return ""


def _produce_only_executor(model_exec: WorkerExecutor, deterministic_exec: WorkerExecutor) -> WorkerExecutor:
    """Use the model only where it creates value: the produce step.

    Brief is an asset audit and review is a verification pass; both are
    deterministic by nature. Letting the model write them only adds a JSON
    failure mode (a non-JSON reply blocks the whole mission).
    """

    def _run(item, worker_id):
        step = str(item.task_id).rsplit(":", 1)[-1]
        if step in {"brief", "review"}:
            return deterministic_exec(item, worker_id)
        return model_exec(item, worker_id)

    return _run


def make_project_onboarding_executor(
    link: ProjectLink,
    spec: DepartmentSpec,
    audit: object,
    plan: str,
    artifacts_root: str | Path,
) -> WorkerExecutor:
    """Executor that turns a real project audit into department deliverables."""

    root = Path(artifacts_root)
    audit_text = render_audit(link, audit)  # type: ignore[arg-type]

    def _execute(item: WorkItem, worker_id: str) -> WorkerExecutionResult:
        step = item.task_id.rsplit(":", 1)[-1]
        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", item.task_id).strip("._") or "task"
        destination = root / safe_task
        destination.mkdir(parents=True, exist_ok=True)

        if step == "brief":
            path = destination / "PROJECT_AUDIT.md"
            path.write_text(audit_text, encoding="utf-8")
            summary = f"{link.name} denetimi: {audit.file_count} dosya"  # type: ignore[attr-defined]
        elif step == "produce":
            path = destination / "INTEGRATION_PLAN.md"
            path.write_text(plan, encoding="utf-8")
            summary = f"{link.name} entegrasyon planı üretildi"
        else:
            path = destination / "deliverable.md"
            path.write_text(
                f"# Kalite kontrolü\n\n{link.name} planı ve denetimi doğrulandı.\n",
                encoding="utf-8",
            )
            summary = f"{link.name} kalite kontrolü tamamlandı"

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary=summary,
            artifacts=(str(path),),
        )

    return _execute


class OwnerConsole:
    """Single owner-facing command surface for the whole holding.

    One line in ("cizgi film departmani kur" / "landing page yap") is enough:
    the console classifies the intent, creates a department when none exists,
    routes the request and runs a real mission through the existing
    manager -> worker -> QA lifecycle.
    """

    def __init__(
        self,
        book: DepartmentBook,
        *,
        runtime_dir: str | Path,
        executors: Mapping[str, WorkerExecutor] | None = None,
        qa_executor: QaExecutor | None = None,
        router: DepartmentRoutingEngine | None = None,
        queue: PersistentMissionQueue | None = None,
        projects: ProjectRegistry | None = None,
        project_roots: tuple[str | Path, ...] = (),
    ) -> None:
        self.book = book
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        from . import worker_metrics

        worker_metrics.configure(self.runtime_dir)
        self.artifacts_root = self.runtime_dir / "artifacts"
        self.queue = queue
        self.projects = projects
        self.project_roots = tuple(Path(root) for root in project_roots)
        # The dashboard growth loop and HTTP commands share one console; the
        # lock keeps queue claims and missions from interleaving.
        self._lock = threading.RLock()
        self._executor_factory: Callable[[], WorkerExecutor] | None = None
        if executors is not None:
            self._explicit_executors = dict(executors)
        else:
            self._explicit_executors = {}
            self._executor_factory = lambda: make_artifact_executor(self.artifacts_root)
        self._qa_executor = qa_executor or local_pass_qa
        self._custom_qa = qa_executor is not None
        self._router = router

    # ------------------------------------------------------------------ public
    def handle(self, text: str) -> ConsoleResult:
        try:
            command = parse_owner_command(text)
        except OwnerCommandError as exc:
            return ConsoleResult(
                kind=CommandKind.HELP,
                status="error",
                message=str(exc),
            )

        if command.kind is CommandKind.HELP:
            return ConsoleResult(
                kind=CommandKind.HELP,
                status="help",
                message=self.help_text(),
            )
        if command.kind is CommandKind.STATUS:
            return self.status_report()

        if command.kind is CommandKind.CREATE_DEPARTMENT:
            return self.create_department(command.domain_text)

        if command.kind is CommandKind.ATTACH_PROJECT:
            return self.attach_project(command.text)

        return self.run_task(command.text)

    def help_text(self) -> str:
        return (
            "Ornek komutlar:\n"
            "- 'cizgi film departmani kur'  -> yeni departman + ekip + ajanlar\n"
            "- 'oyun gelistirme departmani kur' -> oyun studyosu\n"
            "- 'landing page yap'           -> uygun departmana is gonderir\n"
            "- 'Mipiluna projesini oyun departmanina bagla' -> proje + entegrasyon plani\n"
            "- 'durum'                     -> departman ozeti"
        )

    def status_report(self) -> ConsoleResult:
        lines = [f"Holding: {len(self.book.active())} aktif departman"]
        for spec in self.book.active():
            lines.append(
                f"- {spec.name} (`{spec.department_id}`): "
                f"{len(spec.workers)} ajan, {len(spec.capabilities)} yetkinlik"
            )
        return ConsoleResult(
            kind=CommandKind.STATUS,
            status="status_report",
            message="\n".join(lines),
        )

    def create_department(
        self,
        owner_text: str,
        *,
        run_founding_mission: bool = True,
    ) -> ConsoleResult:
        desired = synthesize_department(owner_text)
        existing = self.book.get(desired.department_id)
        upgraded = False

        if existing is None:
            spec = self.book.add(desired)
        elif existing.name == desired.name and len(desired.workers) <= len(
            existing.workers
        ):
            return ConsoleResult(
                kind=CommandKind.CREATE_DEPARTMENT,
                status="department_created",
                message=(
                    f"{existing.name} zaten kurulu (`{existing.department_id}`): "
                    f"{len(existing.workers)} ajan."
                ),
                department_id=existing.department_id,
            )
        elif existing.source == "seed" or len(desired.workers) > len(
            existing.workers
        ):
            # Existing department is smaller than the requested organisation:
            # grow it in place instead of creating a confusing duplicate.
            spec = self.book.add(desired, replace=True)
            upgraded = True
        else:
            department_id = next_available_id(self.book, desired.department_id)
            spec = self.book.add(
                synthesize_department(owner_text, department_id=department_id)
            )

        message = (
            f"{spec.name} kuruldu (`{spec.department_id}`): "
            f"{len(spec.workers)} ajan, {len(spec.capabilities)} yetkinlik."
        )
        if upgraded and existing is not None:
            message = (
                f"{existing.name} büyütüldü ve {spec.name} olarak yapılandırıldı "
                f"(`{spec.department_id}`): {len(spec.workers)} ajan, "
                f"{len(spec.capabilities)} yetkinlik."
            )

        mission: MissionResult | None = None
        if run_founding_mission:
            founding = self.run_department_mission(spec, _FOUNDING_OBJECTIVE)
            mission = founding.mission
            if founding.ok:
                message += " Kuruluş görevi tamamlandı."
            else:
                message += f" Kuruluş görevi tamamlanamadı: {founding.message}"

        return ConsoleResult(
            kind=CommandKind.CREATE_DEPARTMENT,
            status="department_created",
            message=message,
            department_id=spec.department_id,
            mission=mission,
        )

    def attach_project(self, text: str) -> ConsoleResult:
        """Bind a real project folder to a department and produce a plan."""

        name = _project_name_from_text(text)
        if not name:
            return ConsoleResult(
                kind=CommandKind.ATTACH_PROJECT,
                status="error",
                message=(
                    "Proje adı anlaşılamadı. Örnek: "
                    "'Mipiluna projesini oyun departmanına bağla'"
                ),
            )

        spec, _ = self.route(text)
        if spec is None:
            spec = self.route(name)[0]
        if spec is None:
            return ConsoleResult(
                kind=CommandKind.ATTACH_PROJECT,
                status="error",
                message=(
                    f"'{name}' için uygun departman bulunamadı. "
                    "Önce departmanı kurun (ör. 'oyun geliştirme departmanı kur')."
                ),
            )

        project_id = project_id_for(name)
        link = self.projects.get(project_id) if self.projects is not None else None

        if link is None:
            source = resolve_project_source(name, self.project_roots)
            if source is None:
                searched = ", ".join(str(root) for root in self.project_roots) or "-"
                return ConsoleResult(
                    kind=CommandKind.ATTACH_PROJECT,
                    status="error",
                    message=(
                        f"'{name}' için kaynak bulunamadı. Aranan yerler: {searched}. "
                        "Dosyayı bu klasörlerden birine koyun veya yolu komuta ekleyin."
                    ),
                )
            in_place = os.environ.get("AHOS_PROJECT_IN_PLACE", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }
            work_path: Path | None = None
            project_dir_root = self.runtime_dir / "projects" / project_id
            if Path(source).is_dir():
                # Kök asla topluca kopyalanmaz: orijinal yerinde kalır,
                # yalnızca küçük metin kaynakları izole çalışma alanına alınır.
                from .projects import isolate_sources

                path = Path(source)
                work_path = isolate_sources(path, project_dir_root / "work")
            else:
                path = import_project(name, source, project_dir_root)
            audit = audit_project(path, name=name)
            link = ProjectLink(
                project_id=project_id,
                name=name,
                path=path,
                department_id=spec.department_id,
                kind=detect_project_kind(audit),
                source=str(source),
                work_path=work_path,
            )
            if self.projects is not None:
                self.projects.link(link)
        else:
            audit = audit_project(link.path, name=link.name)

        project_dir = self.runtime_dir / "projects" / link.project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        audit_path = project_dir / "PROJECT_AUDIT.md"
        plan_path = project_dir / "INTEGRATION_PLAN.md"
        audit_path.write_text(render_audit(link, audit), encoding="utf-8")

        plan = build_integration_plan(link, spec, audit)
        plan_path.write_text(plan, encoding="utf-8")

        catalog_summary = self._import_tool_catalog(link, project_dir)

        executor = make_project_onboarding_executor(
            link,
            spec,
            audit,
            plan,
            self.artifacts_root,
        )
        onboarding = self.run_department_mission(
            spec,
            f"{link.name} projesini {spec.name} bünyesine bağla ve entegrasyon planını üret",
            executor=executor,
        )

        message = (
            f"{link.name} projesi {spec.name} departmanına bağlandı "
            f"(`{link.project_id}` → `{spec.department_id}`). "
            f"Denetim: {audit.file_count} dosya, {audit.sizes_mb:.1f} MB, tür: {link.kind}. "
            f"Entegrasyon planı: {plan_path}"
        )
        if catalog_summary:
            message += f" Araç kataloğu: {catalog_summary}."
        if onboarding.status != "routed":
            message += f" Onboarding görevi: {onboarding.message}"

        return ConsoleResult(
            kind=CommandKind.ATTACH_PROJECT,
            status="project_linked",
            message=message,
            department_id=spec.department_id,
            mission=onboarding.mission,
        )

    def run_task(self, text: str) -> ConsoleResult:
        spec, score = self.route(text)

        created: str | None = None
        if spec is None:
            spec = self._create_for_task(text)
            created = spec.department_id

        result = self.run_department_mission(spec, text, retry_blocked=True)
        if created is not None:
            result = ConsoleResult(
                kind=CommandKind.TASK,
                status=result.status,
                message=(
                    f"{spec.name} bu iş için kuruldu (`{created}`). "
                    f"{result.message}"
                ),
                department_id=created,
                mission=result.mission,
            )
        return result

    def route(self, text: str) -> tuple[DepartmentSpec | None, int]:
        """Score every department; return the best above the routing threshold."""

        folded = ascii_fold(text)
        registry = self._router_or_default().registry
        engine = DepartmentRoutingEngine(registry)
        decision = engine.route_mission("route", folded)

        scores: dict[str, int] = {
            spec.department_id: spec.keyword_score(text)
            for spec in self.book.active()
        }
        for candidate in decision.candidates:
            key = department_key(candidate.department)
            if key in scores:
                scores[key] += candidate.score

        if not scores:
            return None, 0

        best_id = max(scores, key=lambda key: (scores[key], key))
        best_score = scores[best_id]
        if best_score < ROUTING_THRESHOLD:
            return None, best_score
        return self.book.get(best_id), best_score

    def run_department_mission(
        self,
        spec: DepartmentSpec,
        objective: str,
        *,
        executor: WorkerExecutor | None = None,
        retry_blocked: bool = False,
    ) -> ConsoleResult:
        mission_id = self._mission_id(spec, objective)

        if retry_blocked and self.queue is not None:
            # Açık sahip komutu: daha önce engellenmiş aynı görevi bir kez daha
            # dene. Otonomi kendi sınırlı yeniden-denemesini ayrıca yönetir.
            try:
                existing = self.queue.get(mission_id)
                status = str(getattr(getattr(existing, "status", None), "value", "") or "")
                if status in {"blocked", "failed"}:
                    self.queue.enqueue(
                        mission_id=mission_id,
                        objective=objective,
                        primary_department=spec.department_id,
                        max_attempts=2,
                        replace_existing=True,
                    )
            except Exception:  # noqa: BLE001 - kuyruk isteğe bağlı
                pass

        try:
            from . import live_activity

            live_activity.mission_started(mission_id, spec.department_id, objective)
            self._audit("mission.started", mission_id, {
                "department": spec.department_id, "objective": objective[:160],
            })
            mission = self._dispatch(spec, objective, mission_id, executor)
            self._audit("mission.finished", mission_id, {
                "department": spec.department_id,
                "status": mission.status.value,
                "reason": (mission.reason or "")[:200],
            })
            live_activity.mission_finished(
                mission_id,
                spec.department_id,
                mission.status.value,
                mission.reason,
            )
        except Exception as exc:  # defensive: the console must never crash
            try:
                from . import live_activity

                live_activity.mission_finished(
                    mission_id, spec.department_id, "failed", str(exc)
                )
            except Exception:  # pragma: no cover
                pass
            return ConsoleResult(
                kind=CommandKind.TASK,
                status="error",
                message=f"görev çalıştırılamadı: {type(exc).__name__}: {exc}",
                department_id=spec.department_id,
            )

        return self._console_result(spec, mission)

    def _audit(self, event: str, mission_id: str, payload: dict) -> None:
        try:
            from .audit import AuditLog

            AuditLog(self.runtime_dir / "audit.jsonl").append(
                event, payload, correlation_id=mission_id
            )
        except Exception:  # pragma: no cover - audit must never break work
            pass

    def _console_result(
        self,
        spec: DepartmentSpec,
        mission: MissionResult,
    ) -> ConsoleResult:
        if mission.status is MissionStatus.COMPLETED:
            summary = "; ".join(
                step.worker_summary or step.reason for step in mission.steps
            )
            if not mission.steps and mission.reason:
                # Yürütülmeyen (zaten tamamlanmış) görev: nedeni görünür olsun.
                summary = mission.reason
            return ConsoleResult(
                kind=CommandKind.TASK,
                status="routed",
                message=(
                    f"{spec.name} görevi tamamladı. Adımlar: "
                    f"{len(mission.steps)}. {summary}"
                ),
                department_id=spec.department_id,
                mission=mission,
            )

        return ConsoleResult(
            kind=CommandKind.TASK,
            status="blocked",
            message=f"{spec.name} görevi tamamlayamadı: {mission.reason}",
            department_id=spec.department_id,
            mission=mission,
        )

    # --------------------------------------------------------------- dispatching
    def _dispatch(
        self,
        spec: DepartmentSpec,
        objective: str,
        mission_id: str,
        executor: WorkerExecutor | None = None,
    ) -> MissionResult:
        with self._lock:
            return self._dispatch_serialized(spec, objective, mission_id, executor)

    def _dispatch_serialized(
        self,
        spec: DepartmentSpec,
        objective: str,
        mission_id: str,
        executor: WorkerExecutor | None = None,
    ) -> MissionResult:
        """Persist the mission in the shared queue, then execute it.

        The console reuses the same ``company-service.db`` queue that the control
        center already renders, so owner commands show up next to every other
        mission with their final status and result payload.
        """

        if self.queue is None:
            return self._execute(spec, objective, mission_id, executor)

        owner = "owner-console"
        existing = self.queue.get(mission_id)
        if existing is not None:
            if existing.status in {
                QueueStatus.COMPLETED,
                QueueStatus.WAITING_OWNER_APPROVAL,
                QueueStatus.RUNNING,
                QueueStatus.PENDING,
            }:
                # Terminal veya başka sahipçe yürütülen görev yeniden
                # kuyruğa alınmaz; executor hiç çağrılmaz.
                return self._unclaimed_result(mission_id, objective)
            if existing.attempts >= existing.max_attempts:
                return self._unclaimed_result(mission_id, objective)

        self.queue.enqueue(
            mission_id=mission_id,
            objective=objective,
            primary_department=spec.department_id,
            replace_existing=True,
        )

        for _ in range(200):
            claimed = self.queue.claim_next(owner=owner)
            if claimed is None:
                break

            claimed_spec = self.book.get(claimed.primary_department)
            if claimed_spec is None:
                self.queue.block(
                    claimed.mission_id,
                    owner=owner,
                    result=MissionResult(
                        mission_id=claimed.mission_id,
                        objective=claimed.objective,
                        manager_id=None,
                        status=MissionStatus.BLOCKED,
                        steps=(),
                        reason=(
                            "department no longer exists: "
                            f"{claimed.primary_department}"
                        ),
                    ),
                )
                continue

            lock_path = self._lock_path_for(claimed_spec)
            if lock_path is not None:
                from . import project_locks

                if not project_locks.acquire(
                    lock_path, mission_id=claimed.mission_id
                ):
                    metadata = project_locks.holder(lock_path) or {}
                    blocked = MissionResult(
                        mission_id=claimed.mission_id,
                        objective=claimed.objective,
                        manager_id=None,
                        status=MissionStatus.BLOCKED,
                        steps=(),
                        reason=(
                            "proje kilidi: sahibi "
                            f"{metadata.get('mission_id') or 'bilinmiyor'} "
                            f"(pid {metadata.get('pid') or '?'}); executor çağrılmadı"
                        ),
                    )
                    self._record(claimed.mission_id, owner, blocked)
                    if claimed.mission_id == mission_id:
                        return blocked
                    continue

            result = self._execute_with_deadline(
                claimed_spec,
                claimed.objective,
                claimed.mission_id,
                executor,
            )
            if lock_path is not None:
                from . import project_locks

                if isinstance(result, tuple) or result is None:
                    # İptal doğrulanamadı: kilit KALIR (aynı projeye ikinci işçi
                    # yazamaz). Yalnız doğrulanmış iptalde bırakılır.
                    if result is None:
                        project_locks.release(
                            lock_path, mission_id=claimed.mission_id
                        )
                else:
                    project_locks.release(
                        lock_path, mission_id=claimed.mission_id
                    )
            if result is None:
                result = self._timeout_result(
                    claimed.mission_id,
                    claimed.objective,
                    verified=True,
                    cancel_safe=getattr(executor, "cancel_safe", False) is True,
                )
            elif isinstance(result, tuple):
                result = self._timeout_result(
                    claimed.mission_id,
                    claimed.objective,
                    verified=False,
                    cancel_safe=getattr(executor, "cancel_safe", False) is True,
                )
            self._record(claimed.mission_id, owner, result)
            if claimed.mission_id == mission_id:
                return result

        # Sahiplenilemeyen görev ASLA yürütülmez: başka sahibin lease'i olabilir,
        # görev bitmiş olabilir veya yeniden deneme hakkı kalmamıştır.
        return self._unclaimed_result(mission_id, objective)

    def _mission_deadline_seconds(self) -> float:
        import os

        try:
            value = float(os.environ.get("AHOS_MISSION_TIMEOUT_SECONDS", "300"))
        except ValueError:
            value = 300.0
        return max(1.0, value)

    def _execute_with_deadline(
        self,
        spec: DepartmentSpec,
        objective: str,
        mission_id: str,
        executor: WorkerExecutor | None = None,
    ):
        """Run the mission in a worker thread and enforce a hard deadline.

        Returns ``None`` when the deadline expired; the caller records the
        mission as blocked with a timeout reason. The worker thread is a daemon
        so an unresponsive executor can never keep the panel alive.
        """

        import threading

        from .mission_guard import MissionToken, activate, deactivate

        deadline = self._mission_deadline_seconds()
        token = MissionToken(mission_id)
        box: dict[str, object] = {}

        def _run() -> None:
            activate(token)
            try:
                box["result"] = self._execute(spec, objective, mission_id, executor)
            except BaseException as exc:  # noqa: BLE001 - surfaced to caller
                box["error"] = exc
            finally:
                deactivate()
                token.finished.set()

        thread = threading.Thread(
            target=_run, name=f"mission-{mission_id}", daemon=True
        )
        thread.start()
        thread.join(deadline)
        if thread.is_alive():
            # İptal: token geri alınır, işçi bir sonraki yazma kapısında durur.
            token.revoke()
            cancelled = token.finished.wait(self._cancel_wait_seconds())
            try:
                from . import live_activity

                live_activity.drop_mission(mission_id)
            except Exception:  # pragma: no cover - defensive
                pass
            return None if cancelled else ("unverified", token)
        if "error" in box:
            raise box["error"]  # type: ignore[misc]
        return box["result"]

    def _cancel_wait_seconds(self) -> float:
        import os

        try:
            value = float(os.environ.get("AHOS_CANCEL_WAIT_SECONDS", "2"))
        except ValueError:
            value = 2.0
        return max(0.1, value)

    def _timeout_result(
        self,
        mission_id: str,
        objective: str,
        *,
        verified: bool = True,
        cancel_safe: bool = False,
    ) -> MissionResult:
        suffix = (
            "iptal doğrulandı (işçi durdu)"
            if verified
            else "iptal DOĞRULANAMADI (işçi hâlâ çalışıyor olabilir)"
        )
        if not cancel_safe:
            suffix += "; yürütücü kesilebilir değil (izole süreç desteği yok)"
        return MissionResult(
            mission_id=mission_id,
            objective=objective,
            manager_id=None,
            status=MissionStatus.BLOCKED,
            steps=(),
            reason=(
                "timeout: görev "
                f"{self._mission_deadline_seconds():.0f}s sınırını aştı; {suffix}"
            ),
        )

    def _lock_path_for(self, spec: DepartmentSpec):
        project = self._project_for_department(spec.department_id)
        if project is None:
            return None
        return project.work_path or project.path

    def _unclaimed_result(self, mission_id: str, objective: str) -> MissionResult:
        """Outcome for a mission we could not claim (executor never runs)."""

        existing = self.queue.get(mission_id) if self.queue is not None else None
        if existing is None:
            return MissionResult(
                mission_id=mission_id,
                objective=objective,
                manager_id=None,
                status=MissionStatus.BLOCKED,
                steps=(),
                reason="görev kuyruğa alınamadı (executor çağrılmadı)",
            )
        if existing.status is QueueStatus.COMPLETED:
            return MissionResult(
                mission_id=mission_id,
                objective=objective,
                manager_id=None,
                status=MissionStatus.COMPLETED,
                steps=(),
                reason="görev zaten tamamlanmış; yeniden yürütülmedi",
            )
        return MissionResult(
            mission_id=mission_id,
            objective=objective,
            manager_id=None,
            status=MissionStatus.BLOCKED,
            steps=(),
            reason=(
                "görev sahiplenilemedi "
                f"(durum={existing.status.value}, "
                f"lease={existing.lease_owner or '-'}); executor çağrılmadı"
            ),
        )

    def _record(self, mission_id: str, owner: str, result: MissionResult) -> None:
        assert self.queue is not None
        if result.status is MissionStatus.COMPLETED:
            self.queue.complete(mission_id, owner=owner, result=result)
        elif result.status is MissionStatus.WAITING_OWNER_APPROVAL:
            self.queue.wait_for_owner_approval(
                mission_id,
                owner=owner,
                result=result,
            )
        else:
            self.queue.block(mission_id, owner=owner, result=result)

    def _import_tool_catalog(self, link: ProjectLink, project_dir: Path) -> str | None:
        """Adopt a Harun-style tool catalog + policy into the department."""

        candidates = [
            project_dir / "catalog" / "tools.yaml",
            project_dir / "catalog" / "tools.yml",
        ]
        candidates.extend(project_dir.glob("*/catalog/tools.yaml"))
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                from .tool_catalog import load_catalog, render_catalog_report

                catalog = load_catalog(candidate)
            except Exception:
                continue
            report = render_catalog_report(catalog)
            (project_dir / "TOOL_CATALOG.md").write_text(report, encoding="utf-8")
            return catalog.summary()
        return None

    def _project_for_department(self, department_id: str):
        if self.projects is None:
            return None
        links = self.projects.for_department(department_id)
        return links[0] if links else None

    def _execute(
        self,
        spec: DepartmentSpec,
        objective: str,
        mission_id: str,
        executor: WorkerExecutor | None = None,
    ) -> MissionResult:
        workforce = self.book.workforce()

        if self._explicit_executors:
            executors: dict[str, WorkerExecutor] = dict(self._explicit_executors)
            default = self._explicit_executors.get("*")
            if default is not None:
                for worker in workforce.all():
                    executors.setdefault(worker.profile.worker_id, default)
        else:
            factory = self._executor_factory or (
                lambda: make_artifact_executor(self.artifacts_root)
            )
            project = self._project_for_department(spec.department_id)
            if executor is not None:
                chosen = executor
            elif project is not None:
                settings = (
                    load_settings()
                    if os.environ.get("AHOS_EXECUTOR", "").strip().lower()
                    in {"model", "llm"}
                    else None
                )
                if settings is not None:
                    model_exec = make_model_executor(
                        project.work_path or project.path,
                        self.artifacts_root,
                        settings=settings,
                        spend_ledger=self.runtime_dir / "model-spend.jsonl",
                        require_approval_over_files=3,
                    )
                    deterministic = make_project_executor(
                        project.work_path or project.path,
                        self.artifacts_root,
                    )
                    produce_only = os.environ.get(
                        "AHOS_MODEL_PRODUCE_ONLY", "1"
                    ).strip().lower() not in {"0", "false", "no"}
                    chosen = (
                        _produce_only_executor(model_exec, deterministic)
                        if produce_only
                        else model_exec
                    )
                else:
                    chosen = make_project_executor(
                        project.work_path or project.path,
                        self.artifacts_root,
                    )
            elif spec.department_id == SECURITY_DEPARTMENT_ID:
                chosen = make_guardian_executor(
                    default_repo_root(),
                    self.artifacts_root,
                    journal_path=self.runtime_dir / "security" / "guardian.jsonl",
                )
            else:
                chosen = factory()
            executors = {
                worker.profile.worker_id: chosen for worker in workforce.all()
            }

        from .live_activity import track

        tracked: dict[str, WorkerExecutor] = {}
        for worker_id, worker_executor in executors.items():
            def _wrapped(item, _worker_id, _fn=worker_executor, _wid=worker_id):
                with track(
                    _wid,
                    item.task_id,
                    item.task_id.rsplit(":", 1)[-1],
                    spec.department_id,
                ):
                    return _fn(item, _worker_id)

            tracked[worker_id] = _wrapped
        executors = tracked

        qa_executor = self._qa_executor
        bound_project = self._project_for_department(spec.department_id)
        if bound_project is not None and not self._custom_qa:
            from .project_qa import make_project_qa

            # Denetim izole çalışma alanında yapılır; orijinal kök taranmaz.
            qa_executor = make_project_qa(
                bound_project.work_path or bound_project.path,
                self.artifacts_root,
            )
            from .virtual_workforce import WorkerRole
            # Bound to the actual deterministic QA callable above, with no model.
            verifier_id = "static-web-verifier"
            if not any(w.profile.worker_id == verifier_id for w in workforce.all()):
                workforce.register(WorkerProfile(worker_id=verifier_id,
                    name="Bağımsız statik web doğrulayıcı", role=WorkerRole.QA_ENGINEER,
                    department="quality", capabilities=frozenset({"qa"})))

        # Her görev, üreticiden farklı bağımsız bir doğrulayıcıya sahip olmalı.
        # (review adımını yürüten qa-01 kendi çıktısını onaylayamaz.)
        if not any(w.profile.worker_id == "qa-verify-01" for w in workforce.all()):
            from .virtual_workforce import WorkerRole

            workforce.register(WorkerProfile(
                worker_id="qa-verify-01",
                name="Bağımsız doğrulayıcı",
                role=WorkerRole.QA_ENGINEER,
                department="quality",
                capabilities=frozenset({"qa", "verification"}),
            ))
        if not self._custom_qa and bound_project is None:
            # Bağımsız kabul doğrulayıcısı yok (proje bağlı değil): otomatik
            # geçen local_pass_qa ile görev "tamamlandı" sayılamaz.
            qa_executor = _unverified_qa

        orchestrator = MultiWorkerMissionOrchestrator(
            workforce,
            manager_planner=DepartmentStepPlanner(spec),
            executors=executors,
            qa_executor=qa_executor,
        )

        try:
            return orchestrator.run(
                mission_id=mission_id,
                objective=objective,
                primary_department=spec.department_id,
            )
        except Exception as exc:  # surfaced as a blocked mission, never a crash
            return MissionResult(
                mission_id=mission_id,
                objective=objective,
                manager_id=None,
                status=MissionStatus.BLOCKED,
                steps=(),
                reason=f"{type(exc).__name__}: {exc}",
            )

    # ----------------------------------------------------------------- helpers
    def _router_or_default(self) -> DepartmentRoutingEngine:
        if self._router is not None:
            return self._router
        return DepartmentRoutingEngine(self.book.capability_registry())

    def _create_for_task(self, text: str) -> DepartmentSpec:
        desired = synthesize_department(text)
        department_id = next_available_id(self.book, desired.department_id)
        if department_id != desired.department_id:
            desired = synthesize_department(text, department_id=department_id)
        return self.book.add(desired)

    def _mission_id(self, spec: DepartmentSpec, objective: str) -> str:
        """Deterministic mission id: same department + objective = same mission.

        Using the wall clock here (the old behaviour) meant that two consoles
        submitting the same goal, or the same goal after a restart, produced
        different ids and ran twice. The content hash makes the id stable so the
        queue's primary key is a real duplicate guard.
        """

        import hashlib

        slug = slugify(objective)[:32]
        digest = hashlib.sha256(
            f"{spec.department_id}|{objective.strip().lower()}".encode("utf-8")
        ).hexdigest()[:12]
        return f"CMD-{spec.department_id}-{slug}-{digest}"


def _default_project_roots() -> tuple[Path, ...]:
    env = os.environ.get("AHOS_PROJECT_ROOTS", "")
    if env.strip():
        return tuple(
            Path(item.strip()) for item in env.split(";") if item.strip()
        )
    home = Path.home()
    return tuple(
        root
        for root in (
            home / "Downloads",
            home / "Desktop",
            home / "Documents",
            home / "OneDrive",
            Path.cwd(),
        )
        if root.exists()
    )


def _unverified_qa(item, result, qa_worker_id):
    """Fail-closed QA used when no independent acceptance verifier exists.

    File existence/hash checks prove integrity, not semantic correctness, so a
    department without a bound project cannot self-approve its work.
    """

    from .worker_runtime import QaExecutionResult

    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=False,
        summary=(
            "blocked-unverified: bağımsız kabul doğrulayıcısı yok "
            "(proje bağlı değil); dosya varlığı hash ile doğrulanabilir, "
            "anlamsal doğruluk doğrulanamaz"
        ),
    )


def build_default_console(runtime_dir: str | Path) -> OwnerConsole:
    root = Path(runtime_dir)
    root.mkdir(parents=True, exist_ok=True)
    book = DepartmentBook(root / "departments.json", seed=True)
    ensure_builtin_departments(book)
    queue = PersistentMissionQueue(root / "company-service.db")
    projects = ProjectRegistry(root / "projects.json")
    return OwnerConsole(
        book,
        runtime_dir=root,
        queue=queue,
        projects=projects,
        project_roots=_default_project_roots(),
    )
