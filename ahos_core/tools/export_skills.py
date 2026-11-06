"""Departman bilgisini SKILL.md olarak dışa aktarır (taşınabilir biçim).

Böylece her departmanın araç seti ve çıktı sözleşmesi yalnız bu repoda değil,
`SKILL.md` okuyan her harness'te (Claude Code, Codex, Cursor, Copilot CLI)
kullanılabilir. Kaynak: `ahos.doc_factory.PLAYBOOKS` + `departments.json`.

    python tools/export_skills.py [--out skills] [--runtime-dir PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))

from ahos.doc_factory import PLAYBOOKS  # noqa: E402

TEMPLATE = """---
name: {name}
description: {description}
---

# {title}

Bu beceri, **{title}** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

{when}

## Ücretsiz araç seti

{tools}

## Beklenen çıktılar

{outputs}

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
"""


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- —"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="departman SKILL.md dışa aktarımı")
    parser.add_argument("--out", default=str(CORE.parent / "skills"))
    parser.add_argument("--runtime-dir", default=str(CORE / "runtime"))
    args = parser.parse_args(argv)

    runtime = Path(args.runtime_dir)
    departments_path = runtime / "departments.json"
    names: dict[str, str] = {}
    missions: dict[str, str] = {}
    if departments_path.is_file():
        data = json.loads(departments_path.read_text(encoding="utf-8"))
        for item in data.get("departments", []):
            names[item["department_id"]] = item.get("name") or item["department_id"]
            missions[item["department_id"]] = item.get("mission") or ""

    out = Path(args.out)
    written = []
    for department_id, playbook in PLAYBOOKS.items():
        title = names.get(department_id, department_id)
        folder = out / department_id
        folder.mkdir(parents=True, exist_ok=True)
        text = TEMPLATE.format(
            name=f"{department_id}-department",
            description=f"{title} üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı",
            title=title,
            when=missions.get(department_id) or f"{title} için planlama ve teslim üretimi.",
            tools=_bullets(playbook["araçlar"]),
            outputs=_bullets(playbook["çıktılar"]),
        )
        path = folder / "SKILL.md"
        path.write_text(text, encoding="utf-8")
        written.append(str(path))

    print(json.dumps({"written": len(written), "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
