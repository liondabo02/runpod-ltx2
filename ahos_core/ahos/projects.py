from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .departments import DepartmentSpec, slugify, utc_now

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".gradle",
    "build",
    "dist",
    ".idea",
}

_CODE_SUFFIXES = {".js", ".ts", ".py", ".java", ".kt", ".html", ".css", ".json"}
_DOC_SUFFIXES = {".md", ".txt"}
_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".mp3", ".wav", ".ogg"}


class ProjectError(ValueError):
    """Raised when a project cannot be imported, audited or linked."""


@dataclass(frozen=True, slots=True)
class ProjectAudit:
    path: Path
    name: str
    file_count: int
    total_bytes: int
    directories: tuple[str, ...]
    extensions: tuple[tuple[str, int], ...]
    docs: tuple[str, ...]
    entry_points: tuple[str, ...]
    sizes_mb: float
    has_android: bool
    has_git: bool
    has_package_json: bool
    todo_hits: int
    web_root: str | None = None
    npm_scripts: tuple[str, ...] = ()

    def summary(self) -> str:
        return (
            f"{self.name}: {self.file_count} dosya, {self.sizes_mb:.1f} MB, "
            f"{len(self.directories)} klasör, {len(self.docs)} doküman"
        )


def _iter_files(root: Path, limit: int = 20000) -> Iterable[Path]:
    count = 0
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path
        count += 1
        if count >= limit:
            return


def audit_project(path: str | Path, *, name: str | None = None) -> ProjectAudit:
    root = Path(path)
    if not root.exists() or not root.is_dir():
        raise ProjectError(f"project directory not found: {root}")

    files = list(_iter_files(root))
    extensions: Counter[str] = Counter()
    total_bytes = 0
    docs: list[str] = []
    todos = 0

    for file_path in files:
        suffix = file_path.suffix.lower()
        extensions[suffix or "(yok)"] += 1
        try:
            total_bytes += file_path.stat().st_size
        except OSError:
            pass
        if suffix in _DOC_SUFFIXES:
            docs.append(file_path.name)
        if suffix in {".js", ".ts", ".py", ".java", ".kt", ".html"} and todos < 500:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            todos += len(re.findall(r"\b(TODO|FIXME|HACK)\b", text))

    directories = tuple(
        sorted(
            child.name
            for child in root.iterdir()
            if child.is_dir() and child.name not in IGNORED_DIRS
        )
    )
    entry_candidates = (
        "www/index.html",
        "public/index.html",
        "src/index.html",
        "index.html",
        "package.json",
        "capacitor.config.json",
        "README.md",
        "README-MOBIL.md",
    )
    entry_points = tuple(
        candidate
        for candidate in entry_candidates
        if (root / candidate).exists()
    )

    web_root: str | None = None
    for candidate in ("www", "public", "dist", "build"):
        if (root / candidate / "index.html").exists():
            web_root = candidate
            break
    if web_root is None and (root / "index.html").exists():
        web_root = "."

    npm_scripts: tuple[str, ...] = ()
    package_json = root / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = payload.get("scripts")
            if isinstance(scripts, dict):
                npm_scripts = tuple(sorted(str(key) for key in scripts))
        except (OSError, json.JSONDecodeError):
            npm_scripts = ()

    return ProjectAudit(
        path=root,
        name=name or root.name,
        file_count=len(files),
        total_bytes=total_bytes,
        directories=directories,
        extensions=tuple(extensions.most_common(12)),
        docs=tuple(sorted(docs)[:40]),
        entry_points=entry_points,
        sizes_mb=total_bytes / (1024 * 1024),
        has_android=(root / "android").is_dir(),
        has_git=(root / ".git").exists(),
        has_package_json=(root / "package.json").exists(),
        todo_hits=todos,
        web_root=web_root,
        npm_scripts=npm_scripts,
    )


@dataclass(frozen=True, slots=True)
class ProjectLink:
    project_id: str
    name: str
    path: Path
    department_id: str
    kind: str = "unknown"
    created_at: str = field(default_factory=utc_now)
    source: str = ""
    work_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "path": str(self.path),
            "work_path": str(self.work_path) if self.work_path else None,
            "department_id": self.department_id,
            "kind": self.kind,
            "created_at": self.created_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ProjectLink":
        work = payload.get("work_path")
        return cls(
            project_id=str(payload.get("project_id") or ""),
            name=str(payload.get("name") or ""),
            path=Path(str(payload.get("path") or "")),
            department_id=str(payload.get("department_id") or ""),
            kind=str(payload.get("kind") or "unknown"),
            created_at=str(payload.get("created_at") or utc_now()),
            source=str(payload.get("source") or ""),
            work_path=Path(str(work)) if work else None,
        )


class ProjectRegistry:
    """JSON registry that binds real project folders to departments."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._projects: dict[str, ProjectLink] = {}
        if self.path is not None and self.path.exists():
            self.load()

    def __len__(self) -> int:
        return len(self._projects)

    def all(self) -> tuple[ProjectLink, ...]:
        return tuple(self._projects[key] for key in sorted(self._projects))

    def get(self, project_id: str) -> ProjectLink | None:
        return self._projects.get(project_id)

    def require(self, project_id: str) -> ProjectLink:
        link = self.get(project_id)
        if link is None:
            raise KeyError(f"unknown project: {project_id!r}")
        return link

    def for_department(self, department_id: str) -> tuple[ProjectLink, ...]:
        return tuple(
            link
            for link in self.all()
            if link.department_id == department_id
        )

    def link(self, link: ProjectLink, *, replace: bool = True) -> ProjectLink:
        if not link.project_id:
            raise ProjectError("project_id must not be empty")
        if not link.path.exists():
            raise ProjectError(f"project path does not exist: {link.path}")
        if link.project_id in self._projects and not replace:
            raise ProjectError(f"project already linked: {link.project_id}")
        self._projects[link.project_id] = link
        self.save()
        return link

    def load(self) -> "ProjectRegistry":
        if self.path is None:
            return self
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for item in raw.get("projects") or ():
            link = ProjectLink.from_dict(item)
            self._projects[link.project_id] = link
        return self

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": utc_now(),
            "projects": [link.to_dict() for link in self.all()],
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def resolve_project_source(
    name: str,
    roots: Iterable[str | Path],
    *,
    prefer_suffixes: tuple[str, ...] = (".zip",),
) -> Path | None:
    """Find the newest on-disk artifact that matches a project name."""

    pattern = re.compile(
        rf"(?i)(^|[^a-z]){re.escape(name)}([^a-z]|$)"
    )
    candidates: list[Path] = []

    for root in roots:
        directory = Path(root)
        if not directory.exists():
            continue
        for child in directory.iterdir():
            if child.name.startswith("."):
                continue
            if not pattern.search(child.name):
                continue
            if child.is_file() and child.suffix.lower() not in prefer_suffixes:
                continue
            candidates.append(child)

    if not candidates:
        return None

    def _rank(path: Path) -> tuple[int, float]:
        version = 0
        match = re.search(r"(?i)-v?(\d+)-", path.name)
        if match:
            version = int(match.group(1))
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (version, mtime)

    return max(candidates, key=_rank)


_COPY_IGNORE = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".gradle",
    ".mypy_cache",
    ".ruff_cache",
)


def import_project(
    name: str,
    source: str | Path,
    target_dir: str | Path,
) -> Path:
    """Materialise a project from a zip archive or an existing folder.

    Heavy/generated directories (venv, node_modules, git internals) are skipped
    so binding a large workspace stays fast and path-length safe.
    """

    source_path = Path(source)
    target = Path(target_dir)

    if target.exists() and any(target.iterdir()):
        return target

    if source_path.is_dir():
        import shutil

        target.mkdir(parents=True, exist_ok=True)
        for child in source_path.iterdir():
            if child.name in _COPY_IGNORE:
                continue
            destination = target / child.name
            if child.is_dir():
                shutil.copytree(
                    child,
                    destination,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*_COPY_IGNORE),
                )
            else:
                shutil.copy2(child, destination)
        return target

    if source_path.suffix.lower() != ".zip":
        raise ProjectError(f"unsupported project source: {source_path}")

    target.mkdir(parents=True, exist_ok=True)
    root_resolved = target.resolve()
    with zipfile.ZipFile(source_path) as archive:
        for member in archive.infolist():
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ProjectError(f"unsafe archive member: {member.filename}")
            if any(part in _COPY_IGNORE for part in relative.parts):
                continue
            destination = (target / relative).resolve()
            if root_resolved not in destination.parents and destination != root_resolved:
                raise ProjectError(f"archive member escapes root: {member.filename}")
            archive.extract(member, target)
    return target


def isolate_sources(
    source: str | Path,
    work_dir: str | Path,
    *,
    max_file_bytes: int = 200_000,
    limit: int = 400,
) -> Path:
    """Copy only small text sources into an isolated edit area.

    The original project root is never copied wholesale; heavy directories and
    large binaries stay where they are, and edits happen in `work_dir`.
    """

    import shutil

    root = Path(source)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    suffixes = {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".sh", ".ps1"}
    copied = 0

    for path in root.rglob("*"):
        if copied >= limit:
            break
        if path.is_dir() or any(part in _COPY_IGNORE for part in path.parts):
            continue
        if path.suffix.lower() not in suffixes:
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
        except OSError:
            continue
        relative = path.relative_to(root)
        destination = work / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied += 1

    return work


def detect_project_kind(audit: ProjectAudit) -> str:
    names = {name for name, _ in audit.extensions}
    if audit.has_android and ".html" in names:
        return "capacitor-html5-game"
    if "package.json" in audit.entry_points and "index.html" in audit.entry_points:
        return "web-app"
    if ".py" in names:
        return "python-project"
    if ".html" in names:
        return "html5-app"
    return "unknown"


_PHASES: tuple[tuple[str, str, str], ...] = (
    (
        "1. Envanter ve build doğrulama",
        "Proje iskeleti, bağımlılıklar ve mevcut sürümün yeniden üretilebilir build'i doğrulanır.",
        "platform",
    ),
    (
        "2. Oynanış ve teknik borç denetimi",
        "Kod, performans, hata kaydı ve TODO'lar taranır; en yüksek etkili 10 iyileştirme çıkarılır.",
        "engineering",
    ),
    (
        "3. İçerik üretim hattı",
        "Karakter, hayvan, ses ve bölüm içerikleri üretim hattına bağlanır; üretim kuyruğu kurulur.",
        "art",
    ),
    (
        "4. Kalite ve mağaza sürümü",
        "Regresyon, çocuk güvenliği, performans ve mağaza paketleme kapıları çalıştırılır.",
        "quality",
    ),
    (
        "5. Live-ops ve büyüme",
        "Haftalık içerik takvimi, ölçüm ve gelir modeli kurulur; departman döngüye bağlanır.",
        "growth",
    ),
)


def build_integration_plan(
    link: ProjectLink,
    spec: DepartmentSpec,
    audit: ProjectAudit,
) -> str:
    team_lines = "\n".join(
        f"| `{worker.worker_id}` | {worker.name} | {worker.role} | {worker.team_id} |"
        for worker in spec.workers
    )
    ext_lines = "\n".join(
        f"| `{suffix}` | {count} |" for suffix, count in audit.extensions
    )
    doc_lines = "\n".join(f"- `{doc}`" for doc in audit.docs[:20]) or "- (doküman yok)"
    entry_lines = "\n".join(f"- `{item}`" for item in audit.entry_points) or "- (giriş dosyası tespit edilmedi)"

    phase_lines = "\n".join(
        f"### {title}\n\n{detail}\n\n**Sorumlu ekip:** `{team}`\n"
        for title, detail, team in _PHASES
    )

    return f"""# {link.name} — Departman Entegrasyon Planı

- **Proje:** {link.name} (`{link.project_id}`)
- **Departman:** {spec.name} (`{spec.department_id}`)
- **Tür:** {link.kind}
- **Kaynak:** `{link.source or link.path}`
- **Çalışma dizini:** `{link.path}`
- **Plan üretim zamanı:** {utc_now()}

## 1. Mevcut durum (otomatik envanter)

| Ölçüm | Değer |
| --- | --- |
| Dosya sayısı | {audit.file_count} |
| Toplam boyut | {audit.sizes_mb:.1f} MB |
| Üst seviye klasörler | {", ".join(audit.directories) or "-"} |
| Web kökü | `{audit.web_root or "-"}` |
| npm betikleri | {", ".join(audit.npm_scripts) or "-"} |
| Android paketi | {"var" if audit.has_android else "yok"} |
| Git deposu | {"var" if audit.has_git else "yok"} |
| TODO/FIXME | {audit.todo_hits} |
| Giriş dosyaları | {", ".join(audit.entry_points) or "-"} |

**Dosya türleri**

| Uzantı | Adet |
| --- | --- |
{ext_lines}

**Dokümanlar**

{doc_lines}

**Giriş noktaları**

{entry_lines}

## 2. Aşamalar

{phase_lines}
## 3. Ekip eşlemesi

| Ajan | Ad | Rol | Ekip |
| --- | --- | --- | --- |
{team_lines}

## 4. Riskler ve önlemler

- **Tek dosyada yoğunlaşan oyun kodu**: `family.js` benzeri büyük dosyalar modüllere ayrılmadan
  önce davranış testleri eklenmeli.
- **Mobil paketleme kırılganlığı**: Android build adımları betikleştirilmeli, sürüm numarası
  tek yerden yönetilmeli.
- **İçerik telif ve çocuk güvenliği**: yeni ses/görsel varlıklar için kaynak kaydı ve yaş uygunluğu
  kontrolü zorunlu.
- **Geri dönüş**: her aşama sonunda `git` etiketi + çalışan APK arşivi tutulmalı.

## 5. Kabul kriterleri

1. `index.html` yerel sunucuda hatasız açılır ve ilk oynanış akışı tamamlanır.
2. Otomatik regresyon listesi (en az 10 senaryo) her sürümde çalışır.
3. Android paketi imzalı olarak üretilir ve sürüm numarası plan ile eşleşir.
4. Yeni içerikler departman üretim kuyruğundan geçer; her içerik için kaynak kaydı vardır.
5. Haftalık gelişim döngüsü en az bir iyileştirme görevi tamamlar.

## 6. İlk 7 gün

| Gün | İş | Sorumlu |
| --- | --- | --- |
| 1 | Envanter doğrulama, build'i yeniden üretme | `{spec.department_id}-platform-lead` |
| 2 | Kod taraması ve ilk 10 iyileştirme listesi | `{spec.department_id}-engineering-lead` |
| 3 | Oynanış akışı duman testi | `{spec.department_id}-quality-lead` |
| 4 | Karakter/hayvan envanteri ve eksik listesi | `{spec.department_id}-art-lead` |
| 5 | Ses ve müzik envanteri | `{spec.department_id}-audio-lead` |
| 6 | Mağaza paketleme kontrolü | `{spec.department_id}-platform-lead` |
| 7 | Haftalık değerlendirme ve sonraki sprint | `{spec.department_id}-manager` |
"""


def render_audit(link: ProjectLink, audit: ProjectAudit) -> str:
    ext_lines = "\n".join(
        f"- `{suffix}`: {count}" for suffix, count in audit.extensions
    )
    return f"""# {link.name} — Proje Denetimi

- **Yol:** `{link.path}`
- **Tür:** {link.kind}
- **Dosya:** {audit.file_count} ({audit.sizes_mb:.1f} MB)
- **Android:** {"var" if audit.has_android else "yok"} · **Git:** {"var" if audit.has_git else "yok"}
- **TODO/FIXME:** {audit.todo_hits}

## Üst seviye

{", ".join(audit.directories) or "-"}

## Web kökü

`{audit.web_root or "-"}` · npm betikleri: {", ".join(audit.npm_scripts) or "-"}

## Dosya türleri

{ext_lines}

## Dokümanlar

{", ".join(audit.docs[:15]) or "-"}
"""


def project_id_for(name: str) -> str:
    return slugify(name)
