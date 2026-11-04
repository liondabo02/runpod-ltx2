"""Isci zihni: kalici kimlik, bellek, oz-model, dusunme ve yansima."""
from __future__ import annotations

import json, sqlite3, time
from dataclasses import dataclass, field
from pathlib import Path

MAX_EVENTS = 200


@dataclass
class Mind:
    worker_id: str
    department: str
    role: str = ""
    skills: list = field(default_factory=list)
    events: list = field(default_factory=list)
    self_model: dict = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return round(sum(1 for e in self.events if e.get("ok")) / len(self.events), 3) if self.events else 0.0

    def to_dict(self) -> dict:
        return {"worker_id": self.worker_id, "department": self.department, "role": self.role,
                "skills": self.skills, "events": self.events[-MAX_EVENTS:], "self_model": self.self_model}


def _dir(runtime_dir) -> Path:
    p = Path(runtime_dir) / "minds"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load(runtime_dir, worker_id, department="", role="", skills=None) -> Mind:
    p = _dir(runtime_dir) / f"{worker_id}.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return Mind(d.get("worker_id", worker_id), d.get("department", department), d.get("role", role),
                        d.get("skills") or (skills or []), d.get("events") or [], d.get("self_model") or {})
        except (json.JSONDecodeError, OSError):
            pass
    return Mind(worker_id, department, role, skills or [])


def save(runtime_dir, mind: Mind) -> Path:
    p = _dir(runtime_dir) / f"{mind.worker_id}.json"
    p.write_text(json.dumps(mind.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def think(mind: Mind, ctx: dict) -> str:
    rate = mind.success_rate
    if ctx.get("blocked", 0) > ctx.get("completed", 0):
        stance = "engelleri azaltmaya odaklanmaliyim"
    elif ctx.get("pending", 0) > 8:
        stance = "kuyruk dolu; siradaki isi hizli teslim etmeliyim"
    elif rate >= 0.9 and mind.events:
        stance = "bas  arim yuksek; daha zor gorev isteyebilirim".replace("bas  arim", "basarim")
    elif mind.events:
        stance = "hatalarimi gozden gecirmeliyim"
    else:
        stance = "deneyimim yok; ilk gorevi ogrenerek yapmaliyim"
    return (f"[{mind.department}/{mind.worker_id}] kuyruk: {ctx.get('completed', 0)} tamam, "
            f"{ctx.get('pending', 0)} bekleyen, {ctx.get('blocked', 0)} engel · "
            f"basarim: %{round(rate * 100)} ({len(mind.events)} olay) -> {stance}")


def reflect(mind: Mind) -> dict:
    recent = mind.events[-20:]
    fails = [e for e in recent if not e.get("ok")]
    if fails:
        lesson = f"'{fails[-1].get('kind', 'bilinmeyen')}' turunde hata tekrarlandi; once dogrulama yap."
    elif recent:
        lesson = "son 20 olayda hata yok; mevcut yontem ise yariyor."
    else:
        lesson = "deneyim yok; ilk gorevde not al."
    mind.self_model = {"success_rate": mind.success_rate, "events": len(mind.events),
                       "strength": "istikrar" if mind.success_rate >= 0.9 else "gelisim alani",
                       "lesson": lesson, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return mind.self_model


def _ctx(runtime: Path) -> dict:
    db = runtime / "company-service.db"
    counts = {}
    if db.exists():
        try:
            with sqlite3.connect(db) as con:
                counts = dict(con.execute("select status, count(*) from missions group by status").fetchall())
        except sqlite3.Error:
            counts = {}
    return {"completed": counts.get("completed", 0), "blocked": counts.get("blocked", 0),
            "pending": counts.get("pending", 0)}


def tick(runtime_dir, departments: list, limit: int = 6, seed=None) -> dict:
    runtime = Path(runtime_dir)
    ctx = _ctx(runtime)
    workers = []
    for dep in departments:
        for w in dep.get("workers") or []:
            workers.append((str(w.get("worker_id") or ""), str(dep.get("department_id") or ""),
                            str(w.get("role") or ""), list(w.get("skills") or [])))
    if not workers:
        return {"thoughts": 0, "lessons": 0, "context": ctx}

    chosen = workers[:limit] if len(workers) <= limit else workers[(seed or 0) % len(workers):][:limit]
    inbox = runtime / "knowledge" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    thoughts, lessons = [], 0

    for wid, dep, role, skills in chosen:
        mind = load(runtime, wid, dep, role, skills)
        thought = think(mind, ctx)
        mind.events.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "think", "detail": thought[:300], "ok": True})
        model = reflect(mind)
        save(runtime, mind)
        thoughts.append(thought)
        if "hata" in str(model.get("lesson", "")).lower():
            (inbox / f"ders-{wid}-{int(time.time() * 1000)}.md").write_text(
                f"# {dep}/{wid}\n\n{model['lesson']}\n", encoding="utf-8")
            lessons += 1

    with open(runtime / "minds" / "thoughts.jsonl", "a", encoding="utf-8") as fh:
        for t in thoughts:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "thought": t}, ensure_ascii=False) + "\n")
    return {"thoughts": len(thoughts), "lessons": lessons, "context": ctx}