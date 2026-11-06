from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    description: str
    path: Path
    content_hash: str


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    metadata: SkillMetadata
    body: str


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        raise SkillValidationError("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise SkillValidationError("SKILL.md frontmatter is not closed")
    raw = parts[1].strip()
    body = parts[2].lstrip()

    values: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values, body


def discover_skill(skill_dir: str | Path) -> SkillMetadata:
    path = Path(skill_dir)
    skill_file = path / "SKILL.md"
    if not skill_file.exists():
        raise SkillValidationError(f"missing SKILL.md: {path}")
    text = skill_file.read_text(encoding="utf-8")
    front, _ = _parse_frontmatter(text)

    name = front.get("name", "").strip()
    description = front.get("description", "").strip()

    if not name:
        raise SkillValidationError("skill name is required")
    if not _NAME_RE.fullmatch(name):
        raise SkillValidationError("skill name must be kebab-case")
    if len(name) > 64:
        raise SkillValidationError("skill name exceeds 64 characters")
    if path.name != name:
        raise SkillValidationError(
            f"directory name {path.name!r} must match skill name {name!r}"
        )
    if not description:
        raise SkillValidationError("skill description is required")
    if len(description) > 1024:
        raise SkillValidationError("skill description exceeds 1024 characters")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SkillMetadata(
        name=name,
        description=description,
        path=path,
        content_hash=digest,
    )


def load_skill(skill_dir: str | Path) -> LoadedSkill:
    metadata = discover_skill(skill_dir)
    text = (metadata.path / "SKILL.md").read_text(encoding="utf-8")
    _, body = _parse_frontmatter(text)
    return LoadedSkill(metadata=metadata, body=body)


class SkillRegistry:
    """Agent Skills-compatible registry with progressive disclosure.

    Discovery loads metadata only. Full SKILL.md bodies are loaded only when
    a caller explicitly activates a selected skill.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def discover_all(self) -> tuple[SkillMetadata, ...]:
        if not self.root.exists():
            return ()
        found: list[SkillMetadata] = []
        for item in sorted(self.root.iterdir()):
            if item.is_dir() and (item / "SKILL.md").exists():
                found.append(discover_skill(item))
        return tuple(found)

    def metadata(self, name: str) -> SkillMetadata:
        return discover_skill(self.root / name)

    def activate(self, name: str) -> LoadedSkill:
        return load_skill(self.root / name)
