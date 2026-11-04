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
        set_goal(mind, ctx)
        plan_steps(mind, ctx)
        calibrate(mind)
        to_plan_queue(runtime, mind)
        save(runtime, mind)
        thoughts.append(thought)
        if "hata" in str(model.get("lesson", "")).lower():
            (inbox / f"ders-{wid}-{int(time.time() * 1000)}.md").write_text(
                f"# {dep}/{wid}\n\n{model['lesson']}\n", encoding="utf-8")
            lessons += 1

    share_department_brain(runtime, departments)
    with open(runtime / "minds" / "thoughts.jsonl", "a", encoding="utf-8") as fh:
        for t in thoughts:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "thought": t}, ensure_ascii=False) + "\n")
    return {"thoughts": len(thoughts), "lessons": lessons, "context": ctx}
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

def plan_steps(mind: Mind, ctx: dict) -> list:
    """Hedefi 2-3 somut adima bol; guven tahmini ekle."""
    goal = str((mind.self_model or {}).get("goal") or "")
    if "engelli" in goal:
        steps = ["engelli listeyi cek", "her biri icin neden yaz", "belge yoluyla kapat"]
    elif "kuyruk" in goal:
        steps = ["bekleyenleri say", "en eskiyi al", "teslim et"]
    elif "hata" in goal:
        steps = ["hata sinifini bul", "tek dosyada duzelt", "testle dogrula"]
    elif "zor" in goal:
        steps = ["kapasite kontrol", "uygun gorev sec", "sonucu kaydet"]
    else:
        steps = ["kuyrugu kontrol et", "gorev al", "sonucu kaydet"]
    conf = 0.9 if mind.success_rate >= 0.9 else (0.6 if mind.events else 0.4)
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["plan"] = steps
    mind.self_model["confidence"] = conf
    return steps


def department_brain(runtime_dir, departments: list) -> dict:
    """Departman beyni: uyelerin hedef/guven/plan ozeti."""
    runtime = Path(runtime_dir)
    out = {}
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        members = []
        for w in dep.get("workers") or []:
            wid = str(w.get("worker_id") or "")
            p = runtime / "minds" / f"{wid}.json"
            if p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                m = d.get("self_model") or {}
                members.append({"worker": wid, "goal": m.get("goal", ""), "confidence": m.get("confidence", 0),
                                "plan": m.get("plan", [])})
        goals = {}
        for mem in members:
            goals[mem["goal"]] = goals.get(mem["goal"], 0) + 1
        out[dep_id] = {
            "workers": len(members),
            "top_goal": max(goals, key=goals.get) if goals else "",
            "avg_confidence": round(sum(float(m["confidence"] or 0) for m in members) / len(members), 3) if members else 0,
        }
    return out

def calibrate(mind: Mind) -> float:
    """Guven kalibrasyonu: tahmin ile gercek basariyi karsilastir, faktoru duzelt."""
    model = dict(mind.self_model or {})
    predicted = float(model.get("confidence") or 0.5)
    actual = mind.success_rate if mind.events else 0.5
    error = round(actual - predicted, 3)
    factor = float(model.get("calibration") or 1.0)
    factor = round(max(0.5, min(1.5, factor + error * 0.2)), 3)
    model["calibration"] = factor
    model["calibration_error"] = error
    model["confidence"] = round(max(0.1, min(0.99, predicted + error * 0.3)), 3)
    mind.self_model = model
    return factor


def to_plan_queue(runtime_dir, mind: Mind) -> int:
    """Beynin planini eylem kuyruguna yaz (dosya tabanli)."""
    runtime = Path(runtime_dir)
    steps = list((mind.self_model or {}).get("plan") or [])
    if not steps:
        return 0
    path = runtime / "minds" / "plan-queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for i, step in enumerate(steps):
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "worker": mind.worker_id,
                                 "department": mind.department, "step": i + 1, "action": step,
                                 "state": "pending"}, ensure_ascii=False) + "\n")
    return len(steps)


def share_department_brain(runtime_dir, departments: list) -> dict:
    """Departman ici paylasim: uyelerin dersleri tek beyin dosyasinda toplanir."""
    runtime = Path(runtime_dir)
    out_dir = runtime / "minds" / "departments"
    out_dir.mkdir(parents=True, exist_ok=True)
    shared = {}
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        lessons = []
        for w in dep.get("workers") or []:
            p = runtime / "minds" / f"{w.get('worker_id')}.json"
            if not p.exists():
                continue
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            lesson = str((d.get("self_model") or {}).get("lesson") or "")
            if lesson:
                lessons.append({"worker": d.get("worker_id"), "lesson": lesson})
        unique = []
        for item in lessons:
            if item["lesson"] not in [u["lesson"] for u in unique]:
                unique.append(item)
        payload = {"department": dep_id, "members": len(dep.get("workers") or []),
                   "lessons": unique[:10], "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        (out_dir / f"{dep_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        shared[dep_id] = {"members": payload["members"], "lessons": len(payload["lessons"])}
    return shared


def read_department_brain(runtime_dir, department: str) -> list:
    """Calisan kendi departman beynindeki dersleri okur."""
    p = Path(runtime_dir) / "minds" / "departments" / f"{department}.json"
    if not p.exists():
        return []
    try:
        return list(json.loads(p.read_text(encoding="utf-8")).get("lessons") or [])
    except (json.JSONDecodeError, OSError):
        return []
