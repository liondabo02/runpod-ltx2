"""Departman teslim çalışma alanlarını kurar (idempotent).

Her departman için, eğer bağlı bir projesi yoksa:
  runtime/projects/<dept>-workspace/
    deliverables/            üretilen belgeler
    tools/check_offline.py   bağımsız kabul kapısı (başlık + ≥120 karakter)
  projects.json'a kayıt + kabul kapısının sabitlenmesi

Kullanım:
    python tools/setup_department_workspaces.py [--runtime-dir PATH] [--dry-run]

Not: gerçek üretim yapmaz; yalnızca departmanın teslim edebileceği zemini kurar.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))

from ahos.acceptance_bootstrap import ensure_baseline  # noqa: E402

GATE = '''"""Bagimsiz kabul testi: departman teslimi gercek bir belge mi?"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
deliverables = ROOT / "deliverables"
if not deliverables.is_dir():
    print("kabul testi basarisiz: deliverables dizini yok")
    sys.exit(1)

files = [p for p in deliverables.glob("*.md") if p.is_file()]
if not files:
    print("kabul testi basarisiz: teslim dosyasi yok")
    sys.exit(1)

latest = max(files, key=lambda p: p.stat().st_mtime)
text = latest.read_text(encoding="utf-8", errors="replace")
if len(text.strip()) < 120:
    print(f"kabul testi basarisiz: teslim cok kisa ({len(text.strip())} karakter)")
    sys.exit(1)
if "#" not in text:
    print("kabul testi basarisiz: teslimde baslik yok")
    sys.exit(1)

print(f"kabul testi gecti: {latest.name} ({len(text.strip())} karakter)")
sys.exit(0)
'''

README = """# {name} teslim alanı

Üretilen belgeler `deliverables/` altına yazılır; kabul kapısı
`tools/check_offline.py` bunları başlık ve uzunluk açısından denetler.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="departman teslim alanlarını kur")
    parser.add_argument("--runtime-dir", default=str(CORE / "runtime"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    runtime = Path(args.runtime_dir)
    registry_path = runtime / "projects.json"
    departments_path = runtime / "departments.json"
    evidence = runtime / "artifacts"

    if not departments_path.is_file():
        print(json.dumps({"ok": False, "reason": "departments.json yok"}))
        return 2

    departments = json.loads(departments_path.read_text(encoding="utf-8"))
    rows = departments.get("departments") if isinstance(departments, dict) else departments
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {"projects": []}
    projects = registry.setdefault("projects", [])

    created, skipped = [], []
    for dept in rows or []:
        dept_id = str(dept.get("department_id"))
        name = dept.get("name") or dept_id
        if any(p.get("department_id") == dept_id for p in projects):
            skipped.append(dept_id)
            continue
        if args.dry_run:
            created.append({"department": dept_id, "dry_run": True})
            continue

        root = runtime / "projects" / f"{dept_id}-workspace"
        (root / "deliverables").mkdir(parents=True, exist_ok=True)
        (root / "tools").mkdir(parents=True, exist_ok=True)
        (root / "deliverables" / ".gitkeep").write_text("", encoding="utf-8")
        (root / "README.md").write_text(README.format(name=name), encoding="utf-8")
        (root / "tools" / "check_offline.py").write_text(GATE, encoding="utf-8")
        enrolled, reason = ensure_baseline(root, evidence)

        projects.append({
            "project_id": f"{dept_id}-workspace",
            "name": f"{name} Workspace",
            "path": str(root),
            "work_path": None,
            "department_id": dept_id,
            "kind": "document-workspace",
            "source": "setup_department_workspaces",
        })
        created.append({"department": dept_id, "enrolled": enrolled, "reason": reason})

    if not args.dry_run:
        registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"ok": True, "created": created, "skipped": skipped}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
