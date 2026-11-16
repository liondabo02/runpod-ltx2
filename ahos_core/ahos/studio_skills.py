"""Studio skill kataloğu: SKILL.md dosyalarını yükler ve aranabilir hâle getirir.

Profesyonel beceriler model/araç değildir; ajanların izlemesi gereken
fail-closed üretim prosedürleridir. Bu modül yalnızca yerel `skills/`
dizinini okur; ağ çağrısı yapmaz.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    when_to_use: str
    path: str
    body: str


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Basit YAML frontmatter oku; PyYAML bağımlılığı yok."""

    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if key:
                meta[key] = value.strip()
    return meta, parts[2].lstrip("\n")


def load_skills(root: str | Path | None = None) -> tuple[Skill, ...]:
    """`skills/**/SKILL.md` dosyalarını ada göre sıralı yükle."""

    base = Path(root) if root else SKILLS_DIR
    if not base.is_dir():
        return ()
    skills: list[Skill] = []
    for path in sorted(base.rglob("SKILL.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _frontmatter(text)
        name = meta.get("name") or path.parent.name
        skills.append(Skill(
            name=name,
            description=meta.get("description", ""),
            when_to_use=meta.get("when_to_use", ""),
            path=str(path.relative_to(ROOT)) if ROOT in path.parents else str(path),
            body=body,
        ))
    return tuple(sorted(skills, key=lambda item: item.name))


def find_skill(name: str, root: str | Path | None = None) -> Skill | None:
    for skill in load_skills(root):
        if skill.name == name:
            return skill
    return None


def search_skills(query: str, root: str | Path | None = None) -> tuple[Skill, ...]:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    needle = normalize(query)
    if not needle:
        return load_skills(root)
    return tuple(
        skill for skill in load_skills(root)
        if needle in normalize(skill.name + " " + skill.description + " " + skill.when_to_use)
    )


def render_index(root: str | Path | None = None) -> str:
    rows = ["# AHOS Studio Skills", "",
            "| Skill | Ne zaman | Dosya |", "|---|---|---|"]
    for skill in load_skills(root):
        rows.append(f"| `{skill.name}` | {skill.description or skill.when_to_use} | `{skill.path}` |")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AHOS studio skill kataloğu")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--show", default=None)
    parser.add_argument("--search", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)

    if args.show:
        skill = find_skill(args.show, args.root)
        if skill is None:
            print(json.dumps({"error": "skill bulunamadı", "name": args.show}, ensure_ascii=False))
            return 2
        print(skill.body)
        return 0
    skills = search_skills(args.search or "", args.root)
    if args.json:
        print(json.dumps([skill.__dict__ for skill in skills], ensure_ascii=False, indent=2))
    else:
        print(render_index(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
