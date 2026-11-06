"""Isci zihni: kalici kimlik, bellek, oz-model, dusunme ve yansima."""
from __future__ import annotations

import json, os, sqlite3, time, uuid
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
        # Thoughts, scripted conversations and owner messages are not verified
        # work. Only actual mission outcomes belong in a success percentage.
        observed = [e for e in self.events
                    if e.get("kind") == "mission" and isinstance(e.get("ok"), bool)]
        if not observed:
            return 0.0
        return round(sum(1 for e in observed if e["ok"]) / len(observed), 3)

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
        except (json.JSONDecodeError, OSError) as exc:
            # Never convert a damaged existing memory into an empty worker:
            # a later save() would overwrite the original, losing history.
            raise ValueError(f"worker memory unreadable; original preserved: {p.name}") from exc
        if not isinstance(d, dict):
            raise ValueError(f"worker memory has invalid schema: {p.name}")
        return Mind(d.get("worker_id", worker_id), d.get("department", department), d.get("role", role),
                    d.get("skills") or (skills or []), d.get("events") or [], d.get("self_model") or {})
    return Mind(worker_id, department, role, skills or [])


def save(runtime_dir, mind: Mind) -> Path:
    p = _dir(runtime_dir) / f"{mind.worker_id}.json"
    overflow = mind.events[:-MAX_EVENTS] if len(mind.events) > MAX_EVENTS else []
    if overflow:
        # Archive bounded-context overflow before replacing the active mind.
        # Historical events remain retrievable rather than disappearing at 200.
        archive = p.parent / "archive" / f"{mind.worker_id}.jsonl"
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("a", encoding="utf-8") as stream:
            for event in overflow:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    temp = p.with_name(p.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(mind.to_dict(), ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(temp, p)  # readers see either complete old or new JSON
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.02 * (attempt + 1))
    finally:
        temp.unlink(missing_ok=True)
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
    recent = [e for e in mind.events[-20:]
              if e.get("kind") == "mission" and isinstance(e.get("ok"), bool)]
    fails = [e for e in recent if not e["ok"]]
    if fails:
        lesson = f"'{fails[-1].get('kind', 'bilinmeyen')}' turunde hata tekrarlandi; once dogrulama yap."
    elif recent:
        lesson = "son 20 olayda hata yok; mevcut yontem ise yariyor."
    else:
        lesson = "deneyim yok; ilk gorevde not al."
    # Preserve durable plan scores/strategy. Replacing the entire self model
    # on every tick erased prior mission outcomes and made "learning" vanish.
    model = dict(mind.self_model or {})
    model.update({"success_rate": mind.success_rate, "events": len(mind.events),
                  "strength": "istikrar" if mind.success_rate >= 0.9 else "gelisim alani",
                  "lesson": lesson, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    mind.self_model = model
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


def bootstrap(runtime_dir, departments: list[dict]) -> dict:
    """Give each *rostered* worker persistent operational memory, no invented wins."""
    runtime = Path(runtime_dir)
    initialized = 0
    workers = 0
    for dep in departments:
        department = str(dep.get("department_id") or "")
        for row in dep.get("workers") or []:
            wid = str(row.get("worker_id") or "")
            if not wid or not department:
                continue
            workers += 1
            path = _dir(runtime) / f"{wid}.json"
            if path.exists():
                continue  # existing memory is never overwritten to 'start fresh'
            mind = Mind(worker_id=wid, department=department,
                        role=str(row.get("role") or ""),
                        skills=list(row.get("skills") or []),
                        self_model={
                            "status": "awaiting_verified_work",
                            "goal": "ilk doğrulanabilir görevi bekle",
                            "operational_state": {
                                "label": "beklemede", "simulated": True,
                                "reason": "no observed mission result"
                            },
                            "capability_note": "rule-based memory/reflection; not human consciousness",
                        })
            save(runtime, mind)
            initialized += 1
    return {"rostered": workers, "initialized": initialized}


def tick(runtime_dir, departments: list, limit: int = 6, seed=None) -> dict:
    runtime = Path(runtime_dir)
    if not departments:
        # The background daemon historically passed an empty list, silently
        # starving every worker of periodic reflection and communication.
        book = runtime / "departments.json"
        if book.is_file():
            try:
                payload = json.loads(book.read_text(encoding="utf-8"))
                departments = payload.get("departments", []) if isinstance(payload, dict) else payload
            except (OSError, ValueError, TypeError):
                departments = []
    ctx = _ctx(runtime)
    roster = bootstrap(runtime, departments)
    workers = []
    for dep in departments:
        for w in dep.get("workers") or []:
            wid = str(w.get("worker_id") or "")
            if wid:
                workers.append((wid, str(dep.get("department_id") or ""),
                                str(w.get("role") or ""), list(w.get("skills") or [])))
    if not workers or int(limit) < 1:
        return {"thoughts": 0, "lessons": 0, "context": ctx, "roster": roster}

    cursor_file = _dir(runtime) / ".tick-cursor.json"
    if seed is not None:
        start = int(seed) % len(workers)
    else:
        try:
            start = int(json.loads(cursor_file.read_text(encoding="utf-8")).get("next", 0)) % len(workers)
        except (OSError, ValueError, TypeError, AttributeError):
            start = 0
    chosen = [workers[(start + step) % len(workers)]
              for step in range(min(len(workers), max(0, int(limit))))]
    inbox = runtime / "knowledge" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    thoughts, lessons, memory_errors = [], 0, []

    for wid, dep, role, skills in chosen:
        try:
            mind = load(runtime, wid, dep, role, skills)
        except ValueError:
            memory_errors.append(wid)
            continue  # retain corrupted bytes; do not reset the worker
        thought = think(mind, ctx)
        mind.events.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "kind": "think", "detail": thought[:300],
                            "ok": None})  # simulated reflection is not a QA success
        model = reflect(mind)
        observed = [e for e in mind.events[-30:]
                    if e.get("kind") == "mission" and isinstance(e.get("ok"), bool)]
        failed = sum(1 for e in observed if not e["ok"])
        label = ("yük altında" if ctx.get("pending", 0) >= 240 else
                 "temkinli" if failed > len(observed) // 2 else
                 "odaklı" if observed else "öğrenmeye hazır")
        mind.self_model["operational_state"] = {
            "label": label, "simulated": True,
            "observed_missions": len(observed), "observed_failures": failed,
            "reason": "mission outcomes and queue pressure, not subjective feelings",
        }
        try:
            from .strategy import apply as _apply_strategy
            _apply_strategy(mind)
        except Exception:
            pass
        set_goal(mind, ctx)
        save(runtime, mind)
        thoughts.append(thought)
        if "hata" in str(model.get("lesson", "")).lower():
            (inbox / f"ders-{wid}-{int(time.time() * 1000)}.md").write_text(
                f"# {dep}/{wid}\n\n{model['lesson']}\n", encoding="utf-8")
            lessons += 1

    with open(runtime / "minds" / "thoughts.jsonl", "a", encoding="utf-8") as fh:
        for t in thoughts:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "thought": t}, ensure_ascii=False) + "\n")
    if seed is None:
        # Rotate every cycle; no permanent 'first six workers' bias.
        temporary = cursor_file.with_name(cursor_file.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_text(json.dumps({
                "next": (start + len(chosen)) % len(workers),
                "rostered": len(workers),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }), encoding="utf-8")
            os.replace(temporary, cursor_file)
        finally:
            temporary.unlink(missing_ok=True)
    return {"thoughts": len(thoughts), "lessons": lessons, "context": ctx,
            "roster": roster, "cycled_workers": [item[0] for item in chosen],
            "memory_errors": memory_errors}
def set_goal(mind: Mind, ctx: dict) -> str:
    """Baglamdan somut bir sonraki adim sec (hedef)."""
    if ctx.get("blocked", 0) > 100:
        goal = "engelli gorevleri tasfiye et"
    elif ctx.get("pending", 0) > 8:
        goal = "bekleyen kuyrugu bosalt"
    elif mind.success_rate < 0.7 and mind.events:
        goal = "hatali gorev tipini duzelt"
    elif not mind.events:
        goal = "ilk gorevi al ve tamamla"
    else:
        goal = "daha zor gorev iste"
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["goal"] = goal
    return goal


def summarize(runtime_dir) -> dict:
    """Tum zihinlerin ozeti (panel/ofis icin)."""
    runtime = Path(runtime_dir)
    files = list((runtime / "minds").glob("*.json")) if (runtime / "minds").exists() else []
    rates, goals, thoughts = [], {}, 0
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        model = d.get("self_model") or {}
        rates.append(float(model.get("success_rate", 0)))
        g = str(model.get("goal") or "")
        if g:
            goals[g] = goals.get(g, 0) + 1
    log = runtime / "minds" / "thoughts.jsonl"
    if log.exists():
        thoughts = len(log.read_text(encoding="utf-8", errors="replace").splitlines())
    return {"workers_with_mind": len(files), "avg_success_rate": round(sum(rates) / len(rates), 3) if rates else 0.0,
            "thoughts": thoughts, "top_goals": dict(sorted(goals.items(), key=lambda kv: -kv[1])[:5])}


def emotion(mind: dict, ctx: dict) -> dict:
    """Report simple workload pressure; this is only an operational label."""
    failures = max(0, int(ctx.get("failures", 0)))
    delivered = max(0, int(ctx.get("delivered", 0)))
    mood = "stres" if failures > delivered else "motive"
    mind["mood"] = mood
    return {"mood": mood, "failures": failures, "delivered": delivered}
