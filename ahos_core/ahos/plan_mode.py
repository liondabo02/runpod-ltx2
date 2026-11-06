"""Plan modu — Claude Code / SWE-agent deseninin sadeleştirilmiş hâli.

Fikir: karmaşık görevde modelden önce **deterministik bir plan** üretilir,
plan depoya karşı doğrulanır (dosyalar gerçekten var mı?), sonra adım adım
yürütülür. Böylece "olmayan dosya", "belirsiz hedef" hataları yamadan önce
yakalanır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .targets import mentioned_files


@dataclass(frozen=True)
class Step:
    kind: str          # "read" | "edit" | "verify"
    path: str
    detail: str = ""


@dataclass
class Plan:
    objective: str
    steps: list[Step] = field(default_factory=list)
    problems: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return not self.problems and any(step.kind == "edit" for step in self.steps)

    def text(self) -> str:
        lines = [f"Plan: {self.objective}"]
        lines += [f"{index}. {step.kind} {step.path} {step.detail}".rstrip()
                  for index, step in enumerate(self.steps, start=1)]
        if self.problems:
            lines.append("Sorunlar: " + "; ".join(self.problems))
        return "\n".join(lines)


def build_plan(root: str | Path, objective: str) -> Plan:
    """Görev metninden doğrulanmış plan üretir (model çağrısı yok)."""

    base = Path(root)
    plan = Plan(objective=objective)
    targets = mentioned_files(objective)

    if not targets:
        plan.problems = ("görevde hedef dosya yok",)
        return plan

    existing: list[str] = []
    missing: list[str] = []
    for relative in targets:
        candidate = base / relative
        if candidate.is_file():
            existing.append(relative)
        elif any(base.rglob(Path(relative).name)):
            match = next(base.rglob(Path(relative).name))
            existing.append(match.relative_to(base).as_posix())
        else:
            missing.append(relative)

    for path in existing[:2]:
        plan.steps.append(Step("read", path, "mevcut içeriği oku"))
    if missing:
        plan.problems = tuple(f"hedef yok: {item}" for item in missing)
    for path in existing[:2]:
        plan.steps.append(Step("edit", path, "en küçük değişikliği uygula"))
    if existing:
        plan.steps.append(Step("verify", existing[0], "proje test/kontrol komutunu çalıştır"))
    return plan


def validate_plan(plan: Plan, root: str | Path) -> tuple[bool, tuple[str, ...]]:
    """Planın uygulanabilirliğini yeniden denetler."""

    base = Path(root)
    problems: list[str] = list(plan.problems)
    for step in plan.steps:
        if step.kind in {"read", "edit"} and not (base / step.path).is_file():
            problems.append(f"adım dosyası yok: {step.path}")
    if not any(step.kind == "edit" for step in plan.steps):
        problems.append("planda düzenleme adımı yok")
    return (not problems, tuple(problems))
