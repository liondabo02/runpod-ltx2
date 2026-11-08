from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .departments import utc_now

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".gradle",
}

_SECRET_PATTERNS = (
    (
        re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{15,}"),
        "OpenAI/benzeri API anahtarı",
    ),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "GitHub kişisel erişim anahtarı"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS erişim anahtarı"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "Google API anahtarı"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Özel anahtar"),
)

# Test fixture'ları ve dokümantasyon örnekleri gerçek sır sayılmaz.
_PLACEHOLDER_RE = re.compile(
    r"(?i)(fake|dummy|example|placeholder|sample|abcdefghij|your[-_]?key|xxxx)"
)

_UNPINNED_RE = re.compile(r"^[A-Za-z0-9_.\-\[\]]+\s*(>=|~=|>|<|\^|$)")


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    severity: str
    title: str
    detail: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class GuardianReport:
    repo: Path
    generated_at: str
    findings: tuple[Finding, ...] = ()
    checks: tuple[str, ...] = ()
    branch: str | None = None

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    @property
    def ok(self) -> bool:
        return not self.findings or all(
            finding.severity not in {"critical", "high"} for finding in self.findings
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "repo": str(self.repo),
            "generated_at": self.generated_at,
            "branch": self.branch,
            "ok": self.ok,
            "counts": self.counts,
            "findings": [finding.to_dict() for finding in self.findings],
            "checks": list(self.checks),
        }


def _git_branch(root: Path) -> str | None:
    head = root / ".git" / "HEAD"
    try:
        content = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if content.startswith("ref: refs/heads/"):
        return content[len("ref: refs/heads/") :]
    return content[:12] or None


def _gitignore_patterns(root: Path) -> tuple[str, ...]:
    ignore_file = root / ".gitignore"
    if not ignore_file.exists():
        return ()
    try:
        lines = ignore_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    return tuple(
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    )


def _is_ignored(name: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        cleaned = pattern.rstrip("/")
        if not cleaned:
            continue
        if fnmatch.fnmatch(name, cleaned) or fnmatch.fnmatch(name, cleaned + "/*"):
            return True
        if "/" not in cleaned and name == cleaned:
            return True
    return False


def _iter_text_files(root: Path, limit: int) -> Iterable[Path]:
    count = 0
    for path in root.rglob("*"):
        if path.is_dir() or any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".zip",
            ".aab",
            ".apk",
            ".jar",
            ".wav",
            ".mp3",
            ".ogg",
            ".so",
            ".dll",
            ".exe",
            ".pdf",
        }:
            continue
        try:
            if path.stat().st_size > 400_000:
                continue
        except OSError:
            continue
        yield path
        count += 1
        if count >= limit:
            return


def _walk_files(root: Path, limit: int) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir() or any(part in IGNORED_DIRS for part in path.parts):
            continue
        found.append(path)
        if len(found) >= limit:
            break
    return found


def scan_repository(
    repo_root: str | Path,
    *,
    max_files: int = 1500,
    large_file_mb: float = 20.0,
) -> GuardianReport:
    """Offline, deterministic repository audit (no network, no git binary)."""

    root = Path(repo_root)
    if not root.exists():
        raise FileNotFoundError(f"repository not found: {root}")

    findings: list[Finding] = []
    checks: list[str] = []

    branch = _git_branch(root)
    checks.append("git-head")
    if branch is None:
        findings.append(
            Finding(
                rule_id="git-missing",
                severity="medium",
                title="Git deposu bulunamadı",
                detail="Sürüm kontrolü olmayan bir klasörde çalışılıyor; geri dönüş yok.",
                path=str(root),
            )
        )

    patterns = _gitignore_patterns(root)
    checks.append("gitignore")
    if not patterns:
        findings.append(
            Finding(
                rule_id="gitignore-missing",
                severity="high",
                title=".gitignore yok",
                detail="Anahtar ve build çıktıları yanlışlıkla commit'lenebilir.",
                path=str(root / ".gitignore"),
            )
        )

    files = _walk_files(root, 6000)

    checks.append("secret-files")
    for path in files:
        name = path.name
        if not re.match(r"^\.env", name) or name.endswith(".example"):
            continue
        if _is_ignored(name, patterns):
            continue
        findings.append(
            Finding(
                rule_id="env-not-ignored",
                severity="high",
                title="Ortam dosyası gitignore kapsamında değil",
                detail=(
                    f"`{path.relative_to(root)}` sır içeriyor olabilir ve bir "
                    "`git add -A` ile commit'e girebilir."
                ),
                path=str(path.relative_to(root)),
            )
        )
        if len(findings) > 12:
            break

    checks.append("secret-content")
    hits = 0
    for path in _iter_text_files(root, max_files):
        if hits >= 5:
            break
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in _SECRET_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start : line_end if line_end != -1 else len(text)]
            if _PLACEHOLDER_RE.search(line):
                continue
            hits += 1
            is_fixture = any(
                part.lower() in {"test", "tests", "fixtures", "examples"}
                for part in path.parts
            )
            findings.append(
                Finding(
                    rule_id="secret-in-file",
                    severity="info" if is_fixture else "critical",
                    title=(
                        "Test/örnek dosyada anahtar benzeri metin"
                        if is_fixture
                        else f"Muhtemel sır: {label}"
                    ),
                    detail=(
                        f"`{path.relative_to(root)}` içinde anahtar benzeri metin var; "
                        "gerçek anahtar değilse yok sayılabilir."
                        if is_fixture
                        else (
                            f"`{path.relative_to(root)}` içinde canlı görünen bir "
                            "anahtar bulundu; anahtar döndürülmeli."
                        )
                    ),
                    path=str(path.relative_to(root)),
                )
            )
            break

    checks.append("dependencies")
    for candidate in ("requirements.txt", "requirements-dev.txt"):
        file_path = root / candidate
        if not file_path.exists():
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        unpinned = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
            and _UNPINNED_RE.match(line.strip())
        ]
        if unpinned:
            findings.append(
                Finding(
                    rule_id="unpinned-dependencies",
                    severity="low",
                    title=f"{candidate} içinde sabitlenmemiş bağımlılık",
                    detail=(
                        f"{len(unpinned)} satır tam sürüm sabitlemiyor "
                        f"(ör. {unpinned[0][:60]})."
                    ),
                    path=candidate,
                )
            )

    checks.append("backup-files")
    backups = [
        str(path.relative_to(root))
        for path in files
        if re.search(r"(?i)(\.bak$|\.backup$|before-|\.orig$)", path.name)
    ]
    if backups:
        findings.append(
            Finding(
                rule_id="backup-files",
                severity="low",
                title="Depoda yedek dosyalar var",
                detail="Yedekler sır kopyası taşıyabilir: " + ", ".join(backups[:5]),
                path=str(root),
            )
        )

    checks.append("large-files")
    threshold = large_file_mb * 1024 * 1024
    large: list[str] = []
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= threshold:
            large.append(f"{path.relative_to(root)} ({size / (1024*1024):.1f} MB)")
        if len(large) >= 5:
            break
    if large:
        findings.append(
            Finding(
                rule_id="large-files",
                severity="medium",
                title="Depoda büyük dosyalar",
                detail="; ".join(large),
                path=str(root),
            )
        )

    checks.append("ci")
    workflows = root / ".github" / "workflows"
    if not workflows.exists() or not any(workflows.iterdir()):
        findings.append(
            Finding(
                rule_id="ci-missing",
                severity="low",
                title="CI iş akışı yok",
                detail="Testler otomatik çalışmıyor; regresyon riski artıyor.",
                path=str(workflows),
            )
        )

    return GuardianReport(
        repo=root,
        generated_at=utc_now(),
        findings=tuple(findings),
        checks=tuple(checks),
        branch=branch,
    )


def render_report(report: GuardianReport) -> str:
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings = sorted(
        report.findings,
        key=lambda finding: (severity_order.get(finding.severity, 9), finding.rule_id),
    )

    lines = [
        "# Güvenlik ve Kaynak Koruma Raporu",
        "",
        f"- **Depo:** `{report.repo}`",
        f"- **Dal:** `{report.branch or '-'}`",
        f"- **Zaman:** {report.generated_at}",
        f"- **Durum:** {'TEMİZ' if report.ok else 'AKSİYON GEREKİYOR'}",
        f"- **Bulgu:** {len(findings)} "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(report.counts.items())) or 'yok'})",
        "",
        "## Bulgular",
        "",
    ]
    if not findings:
        lines.append("Kritik veya yüksek riskli bulgu yok.")
    else:
        lines.append("| Önem | Kural | Başlık | Ayrıntı |")
        lines.append("| --- | --- | --- | --- |")
        for finding in findings:
            detail = finding.detail.replace("|", "\\|")[:220]
            lines.append(
                f"| {finding.severity} | `{finding.rule_id}` | {finding.title} | {detail} |"
            )

    lines += ["", "## Yapılan kontroller", ""]
    lines += [f"- `{check}`" for check in report.checks]
    lines.append("")
    return "\n".join(lines)


def next_actions(report: GuardianReport, *, limit: int = 5) -> tuple[str, ...]:
    """Deterministic action list the guardian department works through."""

    actions: list[str] = []
    rules = {finding.rule_id for finding in report.findings}
    if "secret-in-file" in rules:
        actions.append("Sızıntı şüphesi olan dosyadaki anahtarı döndür (rotate) ve geçmişi temizle.")
    if "env-not-ignored" in rules:
        actions.append(".env* dosyalarını .gitignore'a ekle ve yedeklerini depo dışına taşı.")
    if "gitignore-missing" in rules:
        actions.append(".gitignore oluştur (venv, build, .env, node_modules).")
    if "unpinned-dependencies" in rules:
        actions.append("Bağımlılıkları tam sürüme sabitle ve kilit dosyası üret.")
    if "large-files" in rules:
        actions.append("Büyük dosyaları Git LFS'e veya depo dışına taşı.")
    if "ci-missing" in rules:
        actions.append("GitHub Actions ile test + lint iş akışı ekle.")
    if "git-missing" in rules:
        actions.append("Depoyu git ile başlat ve ilk commit'i at.")
    if "backup-files" in rules:
        actions.append("Yedek dosyaları depo dışına al, gerekiyorsa arşivle.")
    if not actions:
        actions.append("Yeni risk yok; haftalık taramayı sürdür.")
    return tuple(actions[:limit])


@dataclass(slots=True)
class GuardianJournal:
    """Append-only JSONL journal so the guardian department has memory."""

    path: Path
    _entries: list[dict[str, object]] = field(default_factory=list)

    def append(self, report: GuardianReport) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "at": report.generated_at,
            "ok": report.ok,
            "counts": report.counts,
            "findings": [finding.rule_id for finding in report.findings],
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def history(self) -> tuple[dict[str, object], ...]:
        if not self.path.exists():
            return ()
        entries = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return tuple(entries)


def default_repo_root() -> Path:
    env = os.environ.get("AHOS_GUARD_REPO", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def make_guardian_executor(
    repo_root: str | Path,
    artifacts_root: str | Path,
    *,
    journal_path: str | Path | None = None,
):
    """Worker executor for the guardian department.

    Every mission produces a real, offline security report of the repository.
    """

    from .worker_runtime import WorkerExecutionResult
    from .workforce_execution import WorkItem

    root = Path(repo_root)
    out_root = Path(artifacts_root)
    journal = GuardianJournal(Path(journal_path)) if journal_path else None

    def _execute(item: WorkItem, worker_id: str):
        report = scan_repository(root)
        if journal is not None:
            journal.append(report)

        step = item.task_id.rsplit(":", 1)[-1]
        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", item.task_id).strip("._") or "task"
        destination = out_root / safe_task
        destination.mkdir(parents=True, exist_ok=True)

        if step == "brief":
            path = destination / "SECURITY_REPORT.md"
            path.write_text(render_report(report), encoding="utf-8")
            summary = (
                f"güvenlik taraması: {len(report.findings)} bulgu, "
                f"durum={'temiz' if report.ok else 'aksiyon gerekli'}"
            )
        elif step == "produce":
            actions = next_actions(report)
            path = destination / "ACTION_PLAN.md"
            path.write_text(
                "# Koruma Aksiyon Planı\n\n"
                + "\n".join(f"{index}. {action}" for index, action in enumerate(actions, 1))
                + "\n",
                encoding="utf-8",
            )
            summary = f"{len(actions)} koruma aksiyonu üretildi"
        else:
            path = destination / "VERIFY.md"
            path.write_text(
                "# Doğrulama\n\n"
                f"- Depo: `{report.repo}`\n"
                f"- Dal: `{report.branch or '-'}`\n"
                f"- Kritik/yüksek bulgu: {report.counts.get('critical', 0) + report.counts.get('high', 0)}\n",
                encoding="utf-8",
            )
            summary = "koruma doğrulaması yapıldı"

        (destination / "findings.json").write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary=summary,
            artifacts=(str(path),),
        )

    return _execute


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(
        prog="ahos-guardian",
        description="Depo güvenlik taraması (offline).",
    )
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = scan_repository(Path(args.repo))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_report(report))
    return 0 if report.ok else 2
