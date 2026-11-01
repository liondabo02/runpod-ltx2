"""Idea intake: the owner's idea becomes department tasks.

The owner does not have to phrase work as a ticket. They say "çocuklar için yeni
bir oyun yapmak istiyorum"; the holding routes the idea to the right department,
breaks it into concrete tasks and stores them. The daemon picks those tasks up
and works them 24/7 — online with a model, offline with the deterministic
catalogue.

Everything is persisted in ``runtime/ideas/`` so a restart never loses an idea.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from .studio_lock import idea_writer

def _write_idea(path, payload):
    # Keep the previous committed idea intact during transient Windows locks.
    import os
    import time
    import uuid
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


TASK_TEMPLATES = (
    ("cekirdek", "temel akisi kur ve calistir"),
    ("arayuz", "kullanici arayuzunu ekle ve dogrula"),
    ("kalite", "kabul testi ve hata sinirini ekle"),
)


def _standard_limit(task: dict) -> int:
    try:
        return min(3, max(1, int(task.get('max_attempts', 2))))
    except (TypeError, ValueError, OverflowError):
        return 2


@dataclass
class Idea:
    idea_id: str
    text: str
    department_id: str
    department_name: str
    tasks: list[dict] = field(default_factory=list)
    status: str = "open"

    def to_dict(self) -> dict:
        return {
            "idea_id": self.idea_id,
            "text": self.text,
            "department_id": self.department_id,
            "department_name": self.department_name,
            "tasks": self.tasks,
            "status": self.status,
        }


def _digest(text: str) -> str:
    return hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()[:12]


def _keywords(text: str, limit: int = 6) -> str:
    words = []
    for word in text.replace(",", " ").split():
        cleaned = word.strip(".!?:;()[]\"'")
        if len(cleaned) >= 4 and cleaned.casefold() not in {
            "için", "yapmak", "istiyorum", "olsun", "yeni", "bir", "ile", "ve",
        }:
            words.append(cleaned)
    return " ".join(words[:limit])


def build_tasks(text: str, department_name: str) -> list[dict]:
    from .studio_department import matches, tasks as studio_tasks
    if matches(text, department_name):
        return studio_tasks(text)
    subject = _keywords(text) or text.strip()[:60]
    tasks: list[dict] = []
    for suffix, wording in TASK_TEMPLATES:
        tasks.append(
            {
                "task_id": f"{suffix}",
                "title": f"{department_name}: {subject} {wording}",
                "status": "pending",
            }
        )
    return tasks


@idea_writer
def submit(console, runtime_dir: str | Path, text: str) -> Idea:
    """Route an idea to a department (creating one if needed) and store its tasks."""

    runtime = Path(runtime_dir)
    ideas_dir = runtime / "ideas"
    ideas_dir.mkdir(parents=True, exist_ok=True)

    spec, _score = console.route(text)
    if spec is None:
        spec = console._create_for_task(text)  # noqa: SLF001 - aynı paket
    idea_id = _digest(text)
    existing = _load(ideas_dir / f"{idea_id}.json")
    if existing and any(t.get('workflow') == 'studio-production-v1' for t in existing.get('tasks', [])):
        return Idea(**{key: existing[key] for key in ('idea_id','text','department_id','department_name','tasks','status')})
    idea = Idea(
        idea_id=idea_id,
        text=text.strip(),
        department_id=spec.department_id,
        department_name=spec.name,
        tasks=build_tasks(text, spec.name),
    )
    _write_idea(ideas_dir / f"{idea_id}.json", idea.to_dict())
    return idea


def _load(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def pending_tasks(runtime_dir: str | Path) -> list[tuple[Idea, dict]]:
    """All pending tasks across ideas, oldest idea first."""

    runtime = Path(runtime_dir)
    ideas_dir = runtime / "ideas"
    rows: list[tuple[Idea, dict]] = []
    if not ideas_dir.is_dir():
        return rows
    # Sahibin en son verdiği fikir önce çalışsın ("beklemesin").
    for path in sorted(ideas_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = _load(path)
        if not payload:
            continue
        idea = Idea(
            idea_id=str(payload.get("idea_id") or path.stem),
            text=str(payload.get("text") or ""),
            department_id=str(payload.get("department_id") or ""),
            department_name=str(payload.get("department_name") or ""),
            tasks=list(payload.get("tasks") or []),
            status=str(payload.get("status") or "open"),
        )
        if idea.status == "done":
            continue
        for task in idea.tasks:
            if task.get("status") == "pending":
                if task.get('workflow') == 'studio-production-v1':
                    from .studio_department import ready
                    if not ready(task, idea.tasks):
                        continue
                    if task.get('stage') == 'qa':
                        from .studio_review import approval_matches
                        if not approval_matches(runtime, idea.idea_id):
                            continue
                rows.append((idea, task))
    return rows


@idea_writer
def claim_next(runtime_dir: str | Path) -> tuple[Idea, dict] | None:
    """Mark the next pending task as running and return it."""

    rows = pending_tasks(runtime_dir)
    if not rows:
        return None
    runtime = Path(runtime_dir)
    selected = None
    for idea, task in rows:
        if task.get('workflow') != 'studio-production-v1' and int(task.get('attempts') or 0) >= _standard_limit(task):
            task['status'] = 'blocked'
            task['blocker'] = task.get('blocker') or 'Yeniden deneme sınırı doldu; yeni plan veya kapsam gerekli'
            idea.status = 'blocked'
            _write_idea(runtime / 'ideas' / f'{idea.idea_id}.json', idea.to_dict())
            continue
        selected = idea, task
        break
    if selected is None:
        return None
    idea, task = selected
    path = runtime / "ideas" / f"{idea.idea_id}.json"
    for item in idea.tasks:
        if item is task:
            item["status"] = "running"
            item['attempts'] = item.get('attempts', 0) + 1
    if all(item.get("status") in {"running", "done"} for item in idea.tasks):
        idea.status = "running"
    _write_idea(path, idea.to_dict())
    return idea, task


@idea_writer
def complete(idea_id: str, task_id: str, runtime_dir: str | Path, *, success: bool, blocker: str = '') -> None:
    runtime = Path(runtime_dir)
    path = runtime / "ideas" / f"{idea_id}.json"
    payload = _load(path)
    if not payload:
        return
    for item in payload.get("tasks") or []:
        if item.get("task_id") == task_id:
            if item.get('workflow') == 'studio-production-v1':
                from .studio_department import acceptance
                issues = acceptance(runtime, idea_id, item) if success else [blocker or 'Üretim yürütücüsü başarısız oldu']
                item['blocker'] = '; '.join(issues)
                item['status'] = 'done' if not issues else ('blocked' if success or item.get('attempts',0)>=item.get('max_attempts',2) else 'pending')
            else:
                item['blocker'] = '' if success else (blocker or 'bağımsız teslimat doğrulanmadı')[:300]
                item["status"] = 'done' if success else ('blocked' if item.get('attempts', 0) >= _standard_limit(item) else 'pending')
    if all(item.get("status") == "done" for item in payload.get("tasks") or []):
        payload["status"] = "done"
    elif any(item.get('status') == 'blocked' for item in payload.get('tasks', [])):
        payload['status'] = 'blocked'
    _write_idea(path, payload)


@idea_writer
def recover(runtime_dir: str | Path, *, stale_minutes: int = 15) -> int:
    """Yarıda kalmış fikir görevlerini yeniden kuyruğa al.

    Bir görev "running" işaretlenip süreç çökerse fikir sonsuza kadar bekte
    kalıyordu. Şu an ``stale_minutes``'ten eski running görevler pending olur;
    hiçbir kayıt silinmez.
    """

    import time as _time

    runtime = Path(runtime_dir)
    folder = runtime / "ideas"
    if not folder.is_dir():
        return 0
    recovered = 0
    now = _time.time()
    for path in folder.glob("*.json"):
        payload = _load(path)
        if not payload:
            continue
        try:
            age_minutes = (now - path.stat().st_mtime) / 60
        except OSError:
            continue
        changed = False
        for item in payload.get("tasks") or []:
            if item.get("status") == "running" and age_minutes >= stale_minutes:
                limit = item.get('max_attempts', 2) if item.get('workflow') == 'studio-production-v1' else _standard_limit(item)
                item["status"] = 'blocked' if item.get('attempts', 0) >= limit else 'pending'
                changed = True
                recovered += 1
        if changed:
            if all(item.get("status") == "done" for item in payload.get("tasks") or []):
                payload["status"] = "done"
            else:
                payload["status"] = "open"
            _write_idea(path, payload)
    return recovered


def pending_count(runtime_dir: str | Path) -> int:
    return len(pending_tasks(runtime_dir))


def main(argv: list[str] | None = None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    text = " ".join(args).strip()
    if "--recover" in args:
        runtime = Path("runtime")
        if "--runtime-dir" in args:
            runtime = Path(args[args.index("--runtime-dir") + 1])
        print(f"kurtarılan fikir görevi: {recover(runtime)}")
        return 0
    if not text:
        print('kullanım: python -m ahos.ideas "çocuklar için yeni bir oyun yapmak istiyorum"')
        return 2
    from .owner_console import build_default_console

    runtime = Path("runtime")
    console = build_default_console(runtime)
    idea = submit(console, runtime, text)
    print(f"fikir alındı: {idea.idea_id}")
    print(f"departman  : {idea.department_name} ({idea.department_id})")
    for task in idea.tasks:
        print(f"  - {task['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
