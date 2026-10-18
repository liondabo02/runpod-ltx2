from __future__ import annotations

import json
import time
import uuid
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .business_units import (
    BusinessUnitBlueprint,
    BusinessUnitWorker,
    TeamBlueprint,
)
from .governance import AuthorityLevel
from .registry import Capability, DepartmentCapabilityRegistry
from .virtual_workforce import (
    VirtualWorkforceRegistry,
    WorkerProfile,
    WorkerRole,
    default_virtual_workforce,
)

BOOK_VERSION = 1

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_AUTHORITY_LEVELS = frozenset({"A", "B", "C", "D"})
_DEPARTMENT_STATUSES = frozenset({"active", "paused"})
_MANAGER_ROLE = "department_manager"
_KNOWN_ROLES = frozenset(role.value for role in WorkerRole)


class DepartmentBookError(ValueError):
    """Raised when a department definition or the book itself is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ascii_fold(value: str) -> str:
    """Fold Turkish/German diacritics so routing tokens match reliably."""

    lowered = value.replace("ı", "i").replace("İ", "I")
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.lower()


def slugify(value: str) -> str:
    folded = ascii_fold(value)
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return slug[:64] or "department"


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """A single capability a department can perform, used for owner routing."""

    name: str
    description: str
    authority: str = "B"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DepartmentBookError("capability name must not be empty")
        if not self.description.strip():
            raise DepartmentBookError("capability description must not be empty")
        if self.authority not in _AUTHORITY_LEVELS:
            raise DepartmentBookError("capability authority must be A/B/C/D")

    def to_capability(self, department_id: str) -> Capability:
        return Capability(
            name=self.name,
            department=department_id,
            description=self.description,
            authority=AuthorityLevel(self.authority),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "authority": self.authority,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "CapabilitySpec":
        return cls(
            name=str(payload.get("name") or ""),
            description=str(payload.get("description") or ""),
            authority=str(payload.get("authority") or "B"),
        )


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    """A virtual employee that belongs to exactly one department."""

    worker_id: str
    name: str
    role: str
    team_id: str
    capabilities: frozenset[str]
    reports_to: str | None = None
    authority_level: str = "B"
    paid_ai_enabled: bool = False
    max_parallel_tasks: int = 1
    daily_budget_usd: float = 0.0

    def __post_init__(self) -> None:
        for attribute in ("worker_id", "name", "role", "team_id"):
            if not str(getattr(self, attribute)).strip():
                raise DepartmentBookError(f"{attribute} must not be empty")
        if self.role not in _KNOWN_ROLES and self.role != _MANAGER_ROLE:
            raise DepartmentBookError(f"unknown worker role: {self.role!r}")
        if not self.capabilities:
            raise DepartmentBookError(f"{self.worker_id} must declare capabilities")
        if self.authority_level not in _AUTHORITY_LEVELS:
            raise DepartmentBookError("worker authority_level must be A/B/C/D")
        if self.max_parallel_tasks < 1:
            raise DepartmentBookError("max_parallel_tasks must be >= 1")
        if self.daily_budget_usd < 0:
            raise DepartmentBookError("daily_budget_usd must be >= 0")

    @property
    def is_manager(self) -> bool:
        return self.role == _MANAGER_ROLE

    def to_worker_profile(self, department_id: str) -> WorkerProfile:
        return WorkerProfile(
            worker_id=self.worker_id,
            name=self.name,
            role=WorkerRole(self.role),
            department=department_id,
            capabilities=frozenset(self.capabilities),
            authority_level=self.authority_level,
            max_parallel_tasks=self.max_parallel_tasks,
            daily_budget_usd=self.daily_budget_usd,
            can_use_paid_ai=self.paid_ai_enabled,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "role": self.role,
            "team_id": self.team_id,
            "capabilities": sorted(self.capabilities),
            "reports_to": self.reports_to,
            "authority_level": self.authority_level,
            "paid_ai_enabled": self.paid_ai_enabled,
            "max_parallel_tasks": self.max_parallel_tasks,
            "daily_budget_usd": self.daily_budget_usd,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "WorkerSpec":
        return cls(
            worker_id=str(payload.get("worker_id") or ""),
            name=str(payload.get("name") or ""),
            role=str(payload.get("role") or ""),
            team_id=str(payload.get("team_id") or ""),
            capabilities=frozenset(
                str(item) for item in (payload.get("capabilities") or ())
            ),
            reports_to=(
                str(payload["reports_to"]) if payload.get("reports_to") else None
            ),
            authority_level=str(payload.get("authority_level") or "B"),
            paid_ai_enabled=bool(payload.get("paid_ai_enabled", False)),
            max_parallel_tasks=int(payload.get("max_parallel_tasks", 1)),
            daily_budget_usd=float(payload.get("daily_budget_usd", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class DepartmentSpec:
    """A department (business unit) the holding can route owner commands to."""

    department_id: str
    name: str
    mission: str
    capabilities: tuple[CapabilitySpec, ...]
    workers: tuple[WorkerSpec, ...]
    keywords: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)
    source: str = "seed"
    status: str = "active"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> "DepartmentSpec":
        errors: list[str] = []

        if not _ID_PATTERN.match(self.department_id):
            errors.append(
                "department_id must be lowercase letters, digits and dashes "
                "(2-64 characters)"
            )
        if not self.name.strip():
            errors.append("name must not be empty")
        if not self.mission.strip():
            errors.append("mission must not be empty")
        if self.status not in _DEPARTMENT_STATUSES:
            errors.append("status must be active or paused")

        capability_names = [capability.name for capability in self.capabilities]
        if not capability_names:
            errors.append("department must declare at least one capability")
        if len(capability_names) != len(set(capability_names)):
            errors.append("duplicate capability names detected")

        worker_ids = [worker.worker_id for worker in self.workers]
        if not worker_ids:
            errors.append("department must declare at least one worker")
        if len(worker_ids) != len(set(worker_ids)):
            errors.append("duplicate worker_id detected")

        managers = [worker for worker in self.workers if worker.is_manager]
        if len(managers) != 1:
            errors.append(
                "department must have exactly one department_manager worker"
            )

        workers_by_id = {worker.worker_id: worker for worker in self.workers}
        for worker in self.workers:
            if worker.is_manager:
                if worker.reports_to is not None:
                    errors.append(
                        f"manager {worker.worker_id} must report to the owner"
                    )
                continue
            if worker.reports_to is None:
                errors.append(
                    f"worker {worker.worker_id} must report to another worker"
                )
            elif worker.reports_to not in workers_by_id:
                errors.append(
                    f"worker {worker.worker_id} reports to unknown worker "
                    f"{worker.reports_to}"
                )
            else:
                seen: set[str] = set()
                current = worker
                while current.reports_to is not None:
                    if current.worker_id in seen:
                        errors.append(
                            f"reporting cycle detected at {current.worker_id}"
                        )
                        break
                    seen.add(current.worker_id)
                    parent = workers_by_id.get(current.reports_to)
                    if parent is None:
                        break
                    current = parent

        covered: set[str] = set()
        for worker in self.workers:
            covered.update(worker.capabilities)
        missing = [
            name
            for name in capability_names
            if name not in covered and name.rsplit(".", 1)[-1] not in covered
        ]
        if missing:
            errors.append(
                "capabilities not covered by any worker: " + ", ".join(sorted(missing))
            )

        if errors:
            raise DepartmentBookError("; ".join(sorted(set(errors))))
        return self

    @property
    def manager(self) -> WorkerSpec:
        return next(worker for worker in self.workers if worker.is_manager)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def to_capability_registry_entries(self) -> tuple[Capability, ...]:
        return tuple(
            capability.to_capability(self.department_id)
            for capability in self.capabilities
        )

    def to_worker_profiles(self) -> tuple[WorkerProfile, ...]:
        return tuple(
            worker.to_worker_profile(self.department_id) for worker in self.workers
        )

    def to_business_unit_blueprint(self) -> BusinessUnitBlueprint:
        """Expose the department through the existing business-unit model.

        ``BusinessUnitBlueprint.validate`` stays the single authority gate for
        hierarchy rules, so the owner console never re-implements them.
        """

        teams: list[TeamBlueprint] = []
        for team_id in dict.fromkeys(worker.team_id for worker in self.workers):
            members = [worker for worker in self.workers if worker.team_id == team_id]
            lead = next(
                (worker for worker in members if worker.is_manager),
                members[0],
            )
            teams.append(
                TeamBlueprint(
                    team_id=team_id,
                    name=team_id.replace("-", " ").title(),
                    lead_worker_id=lead.worker_id,
                    mission=f"{self.name}: {lead.name} ekibinin misyonu.",
                )
            )

        blueprint = BusinessUnitBlueprint(
            business_unit_id=self.department_id,
            name=self.name,
            director_worker_id=self.manager.worker_id,
            owner_controlled=True,
            teams=tuple(teams),
            workers=tuple(
                BusinessUnitWorker(
                    worker_id=worker.worker_id,
                    name=worker.name,
                    role_name=worker.role,
                    team_id=worker.team_id,
                    reports_to=worker.reports_to,
                    capabilities=frozenset(worker.capabilities),
                    authority_level=worker.authority_level,
                    paid_ai_enabled=worker.paid_ai_enabled,
                    external_actions_enabled=False,
                )
                for worker in self.workers
            ),
            owner_reserved_decisions=(
                "department_creation",
                "department_closure",
                "budget_approval",
                "external_publishing",
            ),
        )
        return blueprint.validate()

    def keyword_score(self, text: str) -> int:
        """Deterministic keyword overlap used by the owner router."""

        folded = ascii_fold(text)
        tokens = set(re.findall(r"[a-z0-9]+", folded))
        score = 0
        for keyword in self.keywords:
            folded_keyword = ascii_fold(keyword)
            if " " in folded_keyword:
                if folded_keyword in folded:
                    score += 15
            elif folded_keyword in tokens:
                score += 10
        return score

    def to_dict(self) -> dict[str, object]:
        return {
            "department_id": self.department_id,
            "name": self.name,
            "mission": self.mission,
            "capabilities": [item.to_dict() for item in self.capabilities],
            "workers": [item.to_dict() for item in self.workers],
            "keywords": list(self.keywords),
            "created_at": self.created_at,
            "source": self.source,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DepartmentSpec":
        return cls(
            department_id=str(payload.get("department_id") or ""),
            name=str(payload.get("name") or ""),
            mission=str(payload.get("mission") or ""),
            capabilities=tuple(
                CapabilitySpec.from_dict(item)
                for item in (payload.get("capabilities") or ())
            ),
            workers=tuple(
                WorkerSpec.from_dict(item) for item in (payload.get("workers") or ())
            ),
            keywords=tuple(str(item) for item in (payload.get("keywords") or ())),
            created_at=str(payload.get("created_at") or utc_now()),
            source=str(payload.get("source") or "seed"),
            status=str(payload.get("status") or "active"),
        )


_SEED_KEYWORDS: dict[str, tuple[str, ...]] = {
    "software": (
        "yazilim",
        "kod",
        "uygulama",
        "web sitesi",
        "website",
        "landing page",
        "web",
        "site",
        "sayfa",
        "api",
        "backend",
        "frontend",
        "mobil uygulama",
        "software",
        "app",
        "bug",
    ),
    "quality": ("kalite", "test", "qa", "regresyon", "verification"),
    "research": ("arastirma", "analiz", "rapor", "research", "analysis"),
    "infrastructure": (
        "sunucu",
        "deployment",
        "devops",
        "altyapi",
        "monitoring",
        "infrastructure",
    ),
    "data": ("veri", "data", "raporlama", "analytics", "metrik"),
    "creative": (
        "tasarim",
        "icerik",
        "gorsel",
        "creative",
        "design",
        "senaryo",
        "cizgi film",
        "animasyon",
        "video",
    ),
    "marketing": ("pazarlama", "reklam", "sosyal medya", "seo", "marketing"),
    "sales": ("satis", "musteri", "teklif", "sales", "crm"),
    "finance": ("finans", "butce", "maliyet", "finance", "budget"),
    "operations": ("operasyon", "planlama", "koordinasyon", "operations"),
    "support": ("destek", "musteri hizmetleri", "support", "ticket"),
}


_SEED_NAMES: dict[str, str] = {
    "software": "Yazılım Departmanı",
    "quality": "Kalite Departmanı",
    "research": "Araştırma Departmanı",
    "infrastructure": "Altyapı Departmanı",
    "data": "Veri Departmanı",
    "creative": "Kreatif Departmanı",
    "marketing": "Pazarlama Departmanı",
    "sales": "Satış Departmanı",
    "finance": "Finans Departmanı",
    "operations": "Operasyon Departmanı",
    "support": "Müşteri Destek Departmanı",
}


def seed_department_specs(
    profiles: Iterable[WorkerProfile] | None = None,
) -> tuple[DepartmentSpec, ...]:
    """Convert the built-in virtual workforce roster into department specs."""

    roster = tuple(profiles) if profiles is not None else default_virtual_workforce()
    grouped: dict[str, list[WorkerProfile]] = {}
    for profile in roster:
        grouped.setdefault(profile.department, []).append(profile)

    specs: list[DepartmentSpec] = []
    for department_id in sorted(grouped):
        members = grouped[department_id]
        keywords = _SEED_KEYWORDS.get(department_id, (department_id,))
        aliases = ascii_fold(" ".join(keywords))

        capabilities: list[CapabilitySpec] = []
        seen_capabilities: set[str] = set()
        for member in members:
            for skill in sorted(member.capabilities):
                name = f"{department_id}.{skill}"
                if name in seen_capabilities:
                    continue
                seen_capabilities.add(name)
                capabilities.append(
                    CapabilitySpec(
                        name=name,
                        description=(
                            f"{department_id} {skill} capability. "
                            f"Owner keywords: {aliases}. {skill} gorevi."
                        ),
                        authority="A" if skill in {"planning", "routing"} else "B",
                    )
                )

        workers: list[WorkerSpec] = []
        manager = next(
            (member for member in members if member.role is WorkerRole.DEPARTMENT_MANAGER),
            None,
        )
        if manager is None:
            raise DepartmentBookError(
                f"seeded department {department_id} has no department manager"
            )

        workers.append(
            WorkerSpec(
                worker_id=manager.worker_id,
                name=manager.name,
                role=_MANAGER_ROLE,
                team_id=f"{department_id}-leadership",
                capabilities=frozenset(manager.capabilities),
                reports_to=None,
                authority_level=manager.authority_level,
                max_parallel_tasks=manager.max_parallel_tasks,
                daily_budget_usd=manager.daily_budget_usd,
            )
        )

        for member in members:
            if member.worker_id == manager.worker_id:
                continue
            workers.append(
                WorkerSpec(
                    worker_id=member.worker_id,
                    name=member.name,
                    role=member.role.value,
                    team_id=f"{department_id}-delivery",
                    capabilities=frozenset(member.capabilities),
                    reports_to=manager.worker_id,
                    authority_level=member.authority_level,
                    max_parallel_tasks=member.max_parallel_tasks,
                    daily_budget_usd=member.daily_budget_usd,
                )
            )

        specs.append(
            DepartmentSpec(
                department_id=department_id,
                name=f"{_SEED_NAMES.get(department_id, department_id.title())}",
                mission=(
                    f"Deliver {department_id} work for the holding within owner "
                    f"policy. Keywords: {aliases}."
                ),
                capabilities=tuple(capabilities),
                workers=tuple(workers),
                keywords=tuple(keywords),
                source="seed",
            )
        )

    return tuple(specs)


class DepartmentBook:
    """Persistent registry of every department the holding knows about.

    The book is the single source of truth for the owner console: departments
    created by an owner command live here next to the seeded built-ins, and the
    workforce plus routing registry are always derived from it.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        seed: bool = True,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self._departments: dict[str, DepartmentSpec] = {}
        if self.path is not None and self.path.exists():
            self.load()
        elif seed:
            for spec in seed_department_specs():
                self._departments[spec.department_id] = spec
            if self.path is not None:
                self.save()

    # ------------------------------------------------------------------ reading
    def __len__(self) -> int:
        return len(self._departments)

    def __iter__(self) -> Iterator[DepartmentSpec]:
        return iter(self.all())

    def all(self) -> tuple[DepartmentSpec, ...]:
        return tuple(
            self._departments[key] for key in sorted(self._departments)
        )

    def active(self) -> tuple[DepartmentSpec, ...]:
        return tuple(spec for spec in self.all() if spec.is_active)

    def get(self, department_id: str) -> DepartmentSpec | None:
        return self._departments.get(department_id)

    def require(self, department_id: str) -> DepartmentSpec:
        spec = self.get(department_id)
        if spec is None:
            raise KeyError(f"unknown department: {department_id!r}")
        return spec

    def has(self, department_id: str) -> bool:
        return department_id in self._departments

    # ------------------------------------------------------------------ writing
    def add(self, spec: DepartmentSpec, *, replace: bool = False) -> DepartmentSpec:
        spec.validate()
        if spec.department_id in self._departments and not replace:
            raise DepartmentBookError(
                f"department already exists: {spec.department_id!r}"
            )
        self._departments[spec.department_id] = spec
        self.save()
        return spec

    def pause(self, department_id: str) -> DepartmentSpec:
        current = self.require(department_id)
        updated = DepartmentSpec(
            department_id=current.department_id,
            name=current.name,
            mission=current.mission,
            capabilities=current.capabilities,
            workers=current.workers,
            keywords=current.keywords,
            created_at=current.created_at,
            source=current.source,
            status="paused",
        )
        self._departments[department_id] = updated
        self.save()
        return updated

    # --------------------------------------------------------------- persistence
    def to_dict(self) -> dict[str, object]:
        return {
            "version": BOOK_VERSION,
            "updated_at": utc_now(),
            "departments": [spec.to_dict() for spec in self.all()],
        }

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        temporary = self.path.with_name(self.path.name + "." + uuid.uuid4().hex + ".tmp")
        created = False
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                created = True
                stream.write(payload)
            for attempt in range(5):
                try:
                    temporary.replace(self.path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if created:
                temporary.unlink(missing_ok=True)

    def load(self) -> "DepartmentBook":
        if self.path is None:
            return self
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DepartmentBookError(f"cannot read department book: {exc}") from exc

        version = raw.get("version")
        if version != BOOK_VERSION:
            raise DepartmentBookError(
                f"unsupported department book version: {version!r}"
            )

        self._departments = {}
        for item in raw.get("departments") or ():
            spec = DepartmentSpec.from_dict(item)
            self._departments[spec.department_id] = spec
        return self

    # ------------------------------------------------------------------ derived
    def capability_registry(self) -> DepartmentCapabilityRegistry:
        entries: list[Capability] = []
        active = self.active()
        for spec in active:
            entries.extend(spec.to_capability_registry_entries())
        return DepartmentCapabilityRegistry(
            entries,
            extra_departments=[
                spec.department_id for spec in active if not spec.capabilities
            ],
        )

    def worker_profiles(self) -> tuple[WorkerProfile, ...]:
        profiles: list[WorkerProfile] = []
        for spec in self.active():
            profiles.extend(spec.to_worker_profiles())
        return tuple(profiles)

    def workforce(self) -> VirtualWorkforceRegistry:
        return VirtualWorkforceRegistry(self.worker_profiles())
