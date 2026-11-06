from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .autonomous_company import PersistentMissionQueue

_STEP_SUFFIXES = ("brief", "produce", "review")
_STEP_LABELS = {
    "brief": "Analiz",
    "produce": "Üretim",
    "review": "Kalite kontrol",
}
_FILE_LABELS = {
    "PROJECT_AUDIT.md": "Proje denetimi",
    "INTEGRATION_PLAN.md": "Entegrasyon planı",
    "SECURITY_REPORT.md": "Güvenlik raporu",
    "ACTION_PLAN.md": "Koruma aksiyon planı",
    "VERIFY.md": "Doğrulama",
    "deliverable.md": "Teslimat",
    "findings.json": "Ham bulgular (JSON)",
    "ASSET_REPORT.md": "Varlık denetimi",
    "CHANGES.md": "Değişiklik özeti",
    "CHANGES.diff": "Değişiklik kanıtı (diff)",
}


@dataclass(frozen=True, slots=True)
class OutputFile:
    name: str
    path: Path
    size: int
    label: str
    directory: str = ""

    @property
    def is_markdown(self) -> bool:
        return self.path.suffix.lower() == ".md"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "size": self.size,
            "markdown": self.is_markdown,
            "directory": self.directory,
        }


@dataclass(frozen=True, slots=True)
class MissionOutput:
    mission_id: str
    directory: str
    department: str | None
    objective: str | None
    status: str | None
    updated_at: str | None
    steps: tuple[str, ...]
    files: tuple[OutputFile, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "department": self.department,
            "objective": self.objective,
            "status": self.status,
            "updated_at": self.updated_at,
            "steps": list(self.steps),
            "files": [item.to_dict() for item in self.files],
        }


def _split_step(directory_name: str) -> tuple[str, str]:
    for step in _STEP_SUFFIXES:
        suffix = f"_{step}"
        if directory_name.endswith(suffix):
            return directory_name[: -len(suffix)], step
    return directory_name, ""


def _collect_files(directory: Path) -> tuple[OutputFile, ...]:
    files: list[OutputFile] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt", ".diff"}:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        step = _split_step(directory.name)[1]
        base_label = _FILE_LABELS.get(path.name, path.stem.replace("_", " "))
        label = _STEP_LABELS.get(step, base_label) if step else base_label
        if path.name in _FILE_LABELS:
            label = f"{_STEP_LABELS.get(step, '')} · {base_label}".strip(" ·")
        files.append(
            OutputFile(
                name=path.name,
                path=path,
                size=size,
                label=label,
                directory=directory.name,
            )
        )
    return tuple(files)


def build_output_index(
    artifacts_root: str | Path,
    queue: PersistentMissionQueue | None = None,
    *,
    limit: int = 100,
) -> tuple[MissionOutput, ...]:
    """Group every artifact directory by the mission that produced it."""

    root = Path(artifacts_root)
    if not root.exists():
        return ()

    missions: dict[str, dict[str, object]] = {}

    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        mission_id, step = _split_step(directory.name)
        entry = missions.setdefault(
            mission_id,
            {"dirs": [], "steps": set(), "files": [], "mtime": 0.0},
        )
        entry["dirs"].append(directory)  # type: ignore[union-attr]
        if step:
            entry["steps"].add(step)  # type: ignore[union-attr]
        for item in _collect_files(directory):
            entry["files"].append(item)  # type: ignore[union-attr]
        try:
            entry["mtime"] = max(
                float(entry["mtime"]), directory.stat().st_mtime
            )
        except OSError:
            pass

    def _queue_row(mission_id: str):
        if queue is None:
            return None
        try:
            return queue.get(mission_id)
        except Exception:  # pragma: no cover - defensive
            return None

    results: list[MissionOutput] = []
    for mission_id, entry in missions.items():
        row = _queue_row(mission_id)
        files = tuple(sorted(set(entry["files"]), key=lambda item: item.name))  # type: ignore[arg-type]
        if not files:
            continue
        results.append(
            MissionOutput(
                mission_id=mission_id,
                directory=str((entry["dirs"][0]).name),  # type: ignore[index]
                department=(
                    row.primary_department if row is not None else None
                ),
                objective=row.objective if row is not None else None,
                status=row.status.value if row is not None else None,
                updated_at=row.updated_at if row is not None else None,
                steps=tuple(sorted(entry["steps"])),  # type: ignore[arg-type]
                files=files,
            )
        )

    results.sort(
        key=lambda item: (item.updated_at or "", item.mission_id),
        reverse=True,
    )
    return tuple(results[:limit])


# --------------------------------------------------------------------- serving
def resolve_output_file(
    artifacts_root: str | Path,
    directory: str,
    filename: str,
) -> Path:
    """Resolve one artifact file, refusing any path traversal."""

    root = Path(artifacts_root).resolve()
    for value in (directory, filename):
        if not value or "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("path traversal rejected")

    candidate = (root / directory / filename).resolve()
    if candidate.parent.parent != root:
        raise ValueError("path traversal rejected")
    if not candidate.is_file():
        raise FileNotFoundError(str(candidate))
    if candidate.suffix.lower() not in {".md", ".json", ".txt", ".diff"}:
        raise ValueError("unsupported artifact type")
    return candidate


# -------------------------------------------------------------------- markdown
def _inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def markdown_to_html(text: str) -> str:
    """Small, dependency-free markdown subset used by the artifact viewer."""

    lines = text.splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if not line.strip():
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        if line.lstrip().startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            blocks.append(_render_table(table_lines))
            continue

        if line.strip().startswith(("- ", "* ")):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(("- ", "* ")):
                items.append(f"<li>{_inline(lines[index].strip()[2:])}</li>")
                index += 1
            blocks.append("<ul>" + "".join(items) + "</ul>")
            continue

        ordered = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if ordered:
            items = []
            while index < len(lines):
                match = re.match(r"^\s*\d+\.\s+(.*)$", lines[index])
                if not match:
                    break
                items.append(f"<li>{_inline(match.group(1))}</li>")
                index += 1
            blocks.append("<ol>" + "".join(items) + "</ol>")
            continue

        if line.strip().startswith("```"):
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            index += 1
            blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
            continue

        if line.strip().startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip().lstrip(">").strip())
                index += 1
            inner = "<br>".join(_inline(item) for item in quote_lines if item)
            blocks.append(f"<blockquote><p>{inner}</p></blockquote>")
            continue

        paragraph: list[str] = []
        while (
            index < len(lines)
            and lines[index].strip()
            and not lines[index].lstrip().startswith(("|", "- ", "* ", "#", "```", ">"))
            and not re.match(r"^\s*\d+\.\s+", lines[index])
        ):
            paragraph.append(_inline(lines[index].strip()))
            index += 1
        blocks.append("<p>" + "<br>".join(paragraph) + "</p>")

    return "\n".join(blocks)


def _render_table(lines: list[str]) -> str:
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell):
            continue
        rows.append(cells)

    if not rows:
        return ""

    head, *body = rows
    head_html = "".join(f"<th>{_inline(cell)}</th>" for cell in head)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>"
        for row in body
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


_STYLE = """
:root{--bg:#0b1020;--panel:#141b2d;--line:#26324b;--text:#e9eefc;--muted:#9cabca;--accent:#7aa2ff}
*{box-sizing:border-box}
body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text)}
header{padding:22px 28px 8px;display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap}
h1{margin:0;font-size:23px}.sub{color:var(--muted);font-size:13px;margin-top:6px}
a{color:var(--accent);text-decoration:none}
main{padding:14px 28px 48px}
.section{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin-top:16px;overflow:hidden}
.section h2{font-size:15px;margin:0;padding:14px 16px;border-bottom:1px solid var(--line)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;background:#20304a;font-size:11px;color:#c9d6f2}
.card{padding:14px 16px;border-bottom:1px solid var(--line)}
.card:last-child{border-bottom:0}
.mission{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
.mission b{font-size:14px}
.files{margin-top:8px;display:flex;gap:8px;flex-wrap:wrap}
.files a{background:#0e1526;border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:12px}
.doc{padding:20px 24px;line-height:1.65;font-size:14px}
.doc h1{font-size:22px;margin:0 0 14px}.doc h2{font-size:17px;margin:22px 0 8px;padding:0;border:0}
.doc h3{font-size:15px;margin:18px 0 6px}
.doc table{margin:10px 0}
.doc code{background:#0e1526;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:12px}
.doc pre{background:#0e1526;border:1px solid var(--line);border-radius:9px;padding:12px;overflow:auto}
.doc li{margin:4px 0}
.empty{padding:18px 16px;color:var(--muted)}
"""


def render_outputs_page(
    outputs: tuple[MissionOutput, ...],
    projects: list[dict[str, object]] | None = None,
) -> str:
    cards: list[str] = []
    for output in outputs:
        files = "".join(
            f'<a href="/outputs/view?dir={html.escape(item.directory)}'
            f'&amp;file={html.escape(item.name)}">{html.escape(item.label)}'
            f' <span class="badge">{item.size} B</span></a>'
            for item in output.files
        )
        department = html.escape(output.department or "-")
        objective = html.escape((output.objective or output.mission_id)[:180])
        status = html.escape(output.status or "-")
        cards.append(
            '<div class="card"><div class="mission">'
            f"<div><b>{objective}</b><div class=\"sub\">{html.escape(output.mission_id)}</div></div>"
            f'<div><span class="badge">{department}</span> '
            f'<span class="badge">{status}</span></div></div>'
            f'<div class="files">{files}</div></div>'
        )

    body = "".join(cards) or '<div class="empty">Henüz çıktı yok. Panelden bir komut çalıştırın.</div>'

    project_cards: list[str] = []
    for project in projects or ():
        links = "".join(
            f'<a href="/outputs/project?project={html.escape(str(project["project_id"]))}'
            f'&amp;file={html.escape(file_name)}">{html.escape(file_name)}</a>'
            for file_name in project.get("files") or ()
        )
        project_cards.append(
            '<div class="card"><div class="mission">'
            f'<div><b>{html.escape(str(project["name"]))}</b>'
            f'<div class="sub">`{html.escape(str(project["department_id"]))}` departmanı</div></div>'
            "</div>"
            f'<div class="files">{links}</div></div>'
        )
    project_body = "".join(project_cards)

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS Çıktılar</title><style>{_STYLE}</style></head>
<body>
<header><div><h1>Çıktılar ve Teslimatlar</h1>
<div class="sub">{len(outputs)} görev · dosyaya tıklayıp okuyabilirsin</div></div>
<div><a href="/">← Panel</a> · <a href="/office">Ofis</a></div></header>
<main>
{('<div class="section"><h2>Projeler</h2>' + project_body + "</div>") if project_body else ""}
<div class="section"><h2>Üretilen dosyalar</h2>{body}</div>
</main>
</body></html>"""


def render_document_page(title: str, document_path: Path) -> str:
    text = document_path.read_text(encoding="utf-8", errors="replace")
    if document_path.suffix.lower() == ".md":
        body = markdown_to_html(text)
    else:
        body = f"<pre><code>{html.escape(text[:200_000])}</code></pre>"

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — AHOS</title><style>{_STYLE}</style></head>
<body>
<header><div><h1>{html.escape(title)}</h1>
<div class="sub">{html.escape(str(document_path.name))} · {document_path.stat().st_size} bayt</div></div>
<div><a href="/outputs">← Çıktılar</a> · <a href="/">Panel</a></div></header>
<main><div class="section doc">{body}</div></main>
</body></html>"""


def project_documents(projects_json: Path) -> list[dict[str, object]]:
    """Project-level documents (audit + integration plan) for the outputs page."""

    if not projects_json.exists():
        return []
    try:
        payload = json.loads(projects_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    documents: list[dict[str, object]] = []
    for item in payload.get("projects") or ():
        path = Path(str(item.get("path") or ""))
        if not path.exists():
            continue
        files = [
            candidate
            for candidate in (path / "INTEGRATION_PLAN.md", path / "PROJECT_AUDIT.md")
            if candidate.exists()
        ]
        if files:
            documents.append(
                {
                    "project_id": item.get("project_id"),
                    "name": item.get("name"),
                    "department_id": item.get("department_id"),
                    "files": [path_file.name for path_file in files],
                }
            )
    return documents
