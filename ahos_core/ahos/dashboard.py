"""Tek pano: holdingin o anki durumu (Markdown + HTML).

Veri kaynakları (hepsi diskte, hepsi denetlenebilir):
- kuyruk veritabanı (`company-service.db`): görev durumları, son görevler
- `departments.json` / `projects.json`: ajan sayısı, bağlı proje, kapı
- `model-spend.jsonl`: bugüne kadarki model harcaması
- `reports/cadence-*.md`: haftalık ritim özetleri (başlık satırından)

Kullanım:
    python -m ahos.dashboard [--runtime-dir PATH] [--out DIR]
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _queue_stats(db: Path) -> dict:
    if not db.is_file():
        return {"total": 0, "by_status": {}, "recent": []}
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT status, COUNT(*) AS n FROM missions GROUP BY status").fetchall()
    by_status = {row["status"]: row["n"] for row in rows}
    recent = con.execute(
        "SELECT mission_id, status, updated_at FROM missions ORDER BY updated_at DESC LIMIT 8"
    ).fetchall()
    total = sum(by_status.values())
    con.close()
    return {"total": total, "by_status": by_status,
            "recent": [dict(row) for row in recent]}


def _spend(path: Path) -> dict:
    if not path.is_file():
        return {"usd": 0.0, "calls": 0}
    total, calls = 0.0, 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        calls += 1
        total += float(record.get("usd") or 0.0)
    return {"usd": round(total, 4), "calls": calls}


def _departments(runtime: Path) -> list[dict]:
    departments_path = runtime / "departments.json"
    registry_path = runtime / "projects.json"
    baseline_path = runtime / "artifacts" / "acceptance-baseline.json"
    if not departments_path.is_file():
        return []
    data = json.loads(departments_path.read_text(encoding="utf-8"))
    rows = data.get("departments") if isinstance(data, dict) else data
    projects = []
    if registry_path.is_file():
        projects = json.loads(registry_path.read_text(encoding="utf-8")).get("projects", [])
    pinned = set()
    if baseline_path.is_file():
        try:
            pinned = set(json.loads(baseline_path.read_text(encoding="utf-8")))
        except ValueError:
            pinned = set()

    out = []
    for dept in rows or []:
        dept_id = str(dept.get("department_id"))
        project = next((p for p in projects if p.get("department_id") == dept_id), None)
        gate_ready = False
        if project:
            path = Path(str(project.get("work_path") or project.get("path")))
            gate = path / "tools" / "check_offline.py"
            gate_ready = gate.is_file() and str(gate.resolve()).lower() in pinned
        out.append({
            "department": dept_id,
            "name": dept.get("name") or dept_id,
            "workers": len(dept.get("workers") or []),
            "capabilities": len(dept.get("capabilities") or []),
            "project": (project or {}).get("project_id", "—"),
            "kind": (project or {}).get("kind", "—"),
            "gate": gate_ready,
        })
    return out


def _cadence(runtime: Path) -> list[dict]:
    reports = runtime / "reports"
    if not reports.is_dir():
        return []
    out = []
    for path in sorted(reports.glob("cadence-*.md"), reverse=True)[:5]:
        body = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"Sonuç: \*\*(\d+)/(\d+)\*\*", body)
        out.append({
            "file": path.name,
            "completed": int(match.group(1)) if match else None,
            "total": int(match.group(2)) if match else None,
        })
    return out


def collect(runtime_dir: str | Path) -> dict:
    runtime = Path(runtime_dir)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue": _queue_stats(runtime / "company-service.db"),
        "spend": _spend(runtime / "model-spend.jsonl"),
        "departments": _departments(runtime),
        "cadence": _cadence(runtime),
    }


def render_markdown(snapshot: dict) -> str:
    queue = snapshot["queue"]
    by_status = queue["by_status"]
    departments = snapshot["departments"]
    ready = sum(1 for d in departments if d["gate"])
    lines = [
        "# AHOS panosu",
        "",
        f"Üretim: {snapshot['generated_at']}",
        "",
        "## Kuyruk",
        "",
        f"- toplam görev: **{queue['total']}**",
    ]
    for status in sorted(by_status):
        lines.append(f"- {status}: {by_status[status]}")
    lines += [
        "",
        "## Maliyet",
        "",
        f"- model çağrısı: {snapshot['spend']['calls']} · harcama: **{snapshot['spend']['usd']} $**",
        "",
        "## Departmanlar",
        "",
        f"Teslim edebilir (proje + sabitlenmiş kapı): **{ready}/{len(departments)}**",
        "",
        "| Departman | Ajan | Yetkinlik | Proje | Kapı |",
        "|---|---|---|---|---|",
    ]
    for dept in departments:
        lines.append(
            f"| {dept['name']} (`{dept['department']}`) | {dept['workers']} | "
            f"{dept['capabilities']} | {dept['project']} | "
            f"{'var' if dept['gate'] else 'yok'} |"
        )
    if snapshot["cadence"]:
        lines += ["", "## Haftalık ritim", "", "| Rapor | Sonuç |", "|---|---|"]
        for item in snapshot["cadence"]:
            lines.append(f"| {item['file']} | {item['completed']}/{item['total']} |")
    if queue["recent"]:
        lines += ["", "## Son görevler", "", "| Görev | Durum |", "|---|---|"]
        for row in queue["recent"]:
            lines.append(f"| `{row['mission_id']}` | {row['status']} |")
    lines.append("")
    return "\n".join(lines)


def render_html(snapshot: dict) -> str:
    queue = snapshot["queue"]
    departments = snapshot["departments"]
    ready = sum(1 for d in departments if d["gate"])
    status_rows = "".join(
        f"<tr><td>{html.escape(status)}</td><td>{count}</td></tr>"
        for status, count in sorted(queue["by_status"].items())
    )
    dept_rows = "".join(
        "<tr><td>{name}</td><td>{workers}</td><td>{caps}</td><td>{project}</td>"
        "<td class='{gate_class}'>{gate}</td></tr>".format(
            name=html.escape(d["name"]), workers=d["workers"], caps=d["capabilities"],
            project=html.escape(d["project"]),
            gate="var" if d["gate"] else "yok",
            gate_class="ok" if d["gate"] else "bad",
        )
        for d in departments
    )
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><title>AHOS panosu</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f1117; color: #e6e6e6; }}
h1, h2 {{ font-weight: 600; }}
table {{ border-collapse: collapse; margin: .5rem 0 1.5rem; }}
th, td {{ border: 1px solid #2a2f3a; padding: .35rem .6rem; text-align: left; }}
th {{ background: #1a1f2a; }}
.ok {{ color: #57d38c; }} .bad {{ color: #ff7b72; }}
.metric {{ font-size: 1.6rem; margin-right: 2rem; }}
</style></head><body>
<h1>AHOS panosu</h1>
<p>Üretim: {html.escape(snapshot['generated_at'])}</p>
<p><span class="metric">{queue['total']}</span> görev ·
   <span class="metric">{ready}/{len(departments)}</span> teslim edebilir departman ·
   <span class="metric">{snapshot['spend']['usd']} $</span> harcama</p>
<h2>Kuyruk</h2>
<table><tr><th>Durum</th><th>Adet</th></tr>{status_rows}</table>
<h2>Departmanlar</h2>
<table><tr><th>Departman</th><th>Ajan</th><th>Yetkinlik</th><th>Proje</th><th>Kapı</th></tr>
{dept_rows}</table>
</body></html>
"""


def write_panel(runtime_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    runtime = Path(runtime_dir)
    target = Path(out_dir) if out_dir else runtime / "reports"
    target.mkdir(parents=True, exist_ok=True)
    snapshot = collect(runtime)
    md = target / "PANEL.md"
    html_path = target / "panel.html"
    md.write_text(render_markdown(snapshot), encoding="utf-8")
    html_path.write_text(render_html(snapshot), encoding="utf-8")
    return {"markdown": str(md), "html": str(html_path),
            "ready": sum(1 for d in snapshot["departments"] if d["gate"]),
            "departments": len(snapshot["departments"]),
            "queue_total": snapshot["queue"]["total"],
            "spend_usd": snapshot["spend"]["usd"]}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="AHOS panosu")
    parser.add_argument("--runtime-dir", default=str(Path(__file__).resolve().parents[1] / "runtime"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    print(json.dumps(write_panel(args.runtime_dir, args.out), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
