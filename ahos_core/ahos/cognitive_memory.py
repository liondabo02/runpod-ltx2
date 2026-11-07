"""Kalıcı bilişsel hafıza + üstbiliş + işlevsel duygu + kolektif zeka.

`worker_mind` zihnini DEĞİŞTİRMEZ; yanında `runtime/cognition/<worker>.json`
profili tutar (mevcut hafıza korunur). `cognition.py` (öngörü) de ayrı kalır.

Sınır: buradaki "duygu" işlevsel öncelik etiketidir; öznel duygu/bilinç iddiası
yoktur ve yetki, harcama, güvenlik kurallarını değiştiremez.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

SCHEMA = 1
CAPS = {"episodic": 60, "semantic": 80, "procedural": 40, "reflection": 40}
EMOTION_KEYS = ("curiosity", "learning_drive", "confidence", "caution", "workload",
                "collaboration", "recovery", "patience", "quality_drive")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _dir(runtime) -> Path:
    path = Path(runtime) / "cognition"
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_for(runtime, worker_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", worker_id)[:80]
    return _dir(runtime) / f"{safe}.json"


def new_profile(worker_id: str, department: str = "") -> dict:
    return {
        "schema": SCHEMA, "worker_id": worker_id, "department": department,
        "created_at": _now(), "updated_at": _now(),
        "memory": {"episodic": [], "semantic": [], "procedural": [], "working": {},
                   "long_term": {"by_plan": {}, "months": {}, "milestones": []},
                   "shared": []},
        "metacognition": {"samples": 0, "observed_rate": 0.0, "confidence": 0.5,
                          "calibration_gap": 0.0, "error_rate": 0.0},
        "meta_memory": {}, "conflicts": [],
        "emotion": {key: 0.5 for key in EMOTION_KEYS}, "emotion_history": [],
        "reflection": [], "goals": {"current": "", "options": [], "chosen": ""},
        "evidence": {"verified_missions": [], "status": "no_verified_evidence"},
    }


def load(runtime, worker_id: str, department: str = "") -> dict:
    path = path_for(runtime, worker_id)
    if not path.is_file():
        return new_profile(worker_id, department)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cognition profile unreadable; original preserved: {path.name}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"cognition profile schema mismatch: {path.name}")
    return payload


def save(runtime, profile: dict) -> Path:
    profile["updated_at"] = _now()
    path = path_for(runtime, str(profile["worker_id"]))
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(profile, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def record_episode(profile, *, mission_id, outcome, summary="", evidence_ok=False,
                   plan_type="") -> dict:
    entry = {"at": _now(), "mission_id": str(mission_id), "outcome": str(outcome),
             "summary": str(summary)[:300], "plan_type": str(plan_type),
             "evidence_ok": bool(evidence_ok)}
    bucket = profile["memory"]["episodic"]
    bucket.append(entry)
    del bucket[:-CAPS["episodic"]]
    if evidence_ok:
        verified = profile["evidence"].setdefault("verified_missions", [])
        if entry["mission_id"] not in verified:
            verified.append(entry["mission_id"])
            del verified[:-100]
        profile["evidence"]["status"] = "verified"
    return entry


def learn_semantic(profile, *, statement, source, mission_id="", verified=False) -> dict:
    if not verified:
        raise ValueError("semantic memory requires verified evidence")
    entry = {"at": _now(), "statement": str(statement)[:400], "source": str(source),
             "mission_id": str(mission_id), "verified": True}
    bucket = profile["memory"]["semantic"]
    if any(row.get("statement") == entry["statement"] for row in bucket):
        return entry
    bucket.append(entry)
    del bucket[:-CAPS["semantic"]]
    return entry


def learn_procedural(profile, *, plan_type, ok, steps=None) -> dict:
    rows = profile["memory"]["procedural"]
    row = next((item for item in rows if item.get("plan_type") == plan_type), None)
    if row is None:
        row = {"plan_type": plan_type, "ok": 0, "fail": 0, "steps": [], "updated_at": ""}
        rows.append(row)
    row["ok" if ok else "fail"] += 1
    if steps:
        row["steps"] = [str(step)[:160] for step in steps][:8]
    row["updated_at"] = _now()
    row["rate"] = round(row["ok"] / max(1, row["ok"] + row["fail"]), 3)
    return row


def set_working(profile, *, mission_id, objective, steps=None) -> dict:
    profile["memory"]["working"] = {
        "mission_id": str(mission_id), "objective": str(objective)[:400],
        "steps": [str(step)[:160] for step in (steps or [])][:12], "started_at": _now()}
    return profile["memory"]["working"]


def clear_working(profile) -> None:
    profile["memory"]["working"] = {}


def classify_cause(reason: str) -> str:
    text = (reason or "").casefold()
    for name, needles in (
        ("timeout", ("zaman aşımı", "timeout", "timed out")),
        ("model_unavailable", ("model",)),
        ("acceptance_failed", ("kabul", "acceptance")),
        ("no_delivery", ("değişmedi", "değişiklik yok", "no delivery", "changed_files")),
        ("lock", ("kilit", "lock", "lease")),
        ("permission", ("yetki", "permission", "denied")),
        ("schema", ("şema", "schema")),
    ):
        if any(needle in text for needle in needles):
            return name
    return "other"


def metacognition(profile) -> dict:
    episodes = [row for row in profile["memory"]["episodic"] if row.get("evidence_ok") is True]
    if episodes:
        samples = len(episodes)
        ok = sum(1 for row in episodes if row.get("outcome") == "completed")
    else:
        # Kanıtlı olay yoksa yalnız gözlenmiş prosedürel sonuçlar kullanılır.
        rows = profile["memory"]["procedural"]
        samples = sum(int(row.get("ok", 0)) + int(row.get("fail", 0)) for row in rows)
        ok = sum(int(row.get("ok", 0)) for row in rows)
    observed = round(ok / samples, 3) if samples else 0.0
    confidence = round((ok + 1) / (samples + 2), 3)
    result = {"samples": samples, "observed_rate": observed, "confidence": confidence,
              "calibration_gap": round(abs(confidence - observed), 3) if samples else 0.0,
              "error_rate": round(1 - observed, 3) if samples else 0.0,
              "note": ("no verified evidence" if not samples
                       else "derived from verified mission outcomes")}
    profile["metacognition"] = result
    return result


def reflect(profile, *, mission_id, ok, reason="", plan_type="", evidence_ok=False) -> dict:
    cause = "" if ok else classify_cause(reason)
    if not evidence_ok:
        lesson = (f"kanıt yok: {mission_id} için bağımsız QA kaydı olmadan "
                  "başarı ya da ders üretilmedi")
    elif ok:
        lesson = (f"{mission_id}: {plan_type or 'görev'} yolu bağımsız QA ile doğrulandı; "
                  "aynı yol tekrar kullanılabilir")
    else:
        lesson = (f"{mission_id}: {plan_type or 'görev'} yolu {cause} nedeniyle başarısız; "
                  "önce bu nedeni doğrula, kör tekrar yok")
    entry = {"at": _now(), "mission_id": str(mission_id), "ok": bool(ok), "cause": cause,
             "plan_type": str(plan_type), "lesson": lesson,
             "evidence_ok": bool(evidence_ok), "verified": bool(evidence_ok)}
    bucket = profile["reflection"]
    bucket.append(entry)
    del bucket[:-CAPS["reflection"]]
    return entry


def plan_goal(profile, goal: str, options: list[dict]) -> dict:
    ranked = sorted(({"option": str(item.get("option")),
                      "score": _clamp(item.get("score", 0)),
                      "reason": str(item.get("reason") or "")} for item in options),
                    key=lambda row: row["score"], reverse=True)
    profile["goals"] = {"current": str(goal), "options": ranked,
                        "chosen": ranked[0]["option"] if ranked else "", "updated_at": _now()}
    return profile["goals"]


def emotion(profile, *, pending: int = 0, idle: bool = True, last_outcome: str = "") -> dict:
    meta = metacognition(profile)
    confidence = meta["confidence"]
    error_rate = meta["error_rate"]
    workload = _clamp(pending / 240 if pending else 0.0)
    previous = dict(profile.get("emotion") or {})
    state = {
        "curiosity": _clamp(0.35 + (0.35 if idle else 0.0) + (1 - workload) * 0.2
                            - error_rate * 0.25),
        "learning_drive": _clamp(0.30 + (0.35 if idle else 0.05)
                                 + (1 - confidence) * 0.3),
        "confidence": confidence,
        "caution": _clamp(0.2 + error_rate * 0.7),
        "workload": workload,
        "collaboration": _clamp(0.35 + (1 - workload) * 0.25
                                + ((1 - confidence) * 0.6 + workload * 0.4) * 0.2),
        "recovery": _clamp(1.0 if last_outcome == "completed"
                           else (0.15 if last_outcome else float(previous.get("recovery", 0.5)))),
        "patience": _clamp(0.4 + (1 - error_rate) * 0.3 + (1 - workload) * 0.2),
        "quality_drive": _clamp(0.55 + error_rate * 0.35),
    }
    # Geriye dönük uyum: eski profillerde help_seeking alanı korunur.
    state["help_seeking"] = _clamp((1 - confidence) * 0.6 + workload * 0.4)
    profile["emotion"] = state
    history = profile.setdefault("emotion_history", [])
    history.append({"at": _now(), **state})
    del history[:-20]
    return state


def emotion_priority(profile, *, pending: int = 0, idle: bool = True) -> dict:
    state = emotion(profile, pending=pending, idle=idle)
    if state["workload"] >= 0.8:
        mode = "drain_backlog"
    elif state["help_seeking"] >= 0.7:
        mode = "ask_for_help"
    elif state["caution"] >= 0.6:
        mode = "verify_before_retry"
    elif idle:
        mode = "explore_and_learn"
    else:
        mode = "deliver_verified_work"
    return {"mode": mode, "emotion": state, "authority_effect": "none", "spend_effect": "none"}


def _collective_log(runtime) -> Path:
    return _dir(runtime) / "_collective.jsonl"


def _append_collective(runtime, record: dict) -> dict:
    with _collective_log(runtime).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def expert_index(runtime, departments: list[dict]) -> dict:
    index: dict[str, list[dict]] = {}
    for dep in departments:
        department = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            wid = str(worker.get("worker_id") or "")
            if not wid:
                continue
            try:
                profile = load(runtime, wid, department)
            except ValueError:
                continue
            rows = profile["memory"]["procedural"]
            runs = sum(row.get("ok", 0) + row.get("fail", 0) for row in rows)
            ok = sum(row.get("ok", 0) for row in rows)
            rate = round(ok / runs, 3) if runs else None
            for capability in worker.get("capabilities") or worker.get("skills") or []:
                key = str(capability).strip()
                if key:
                    index.setdefault(key, []).append(
                        {"worker": wid, "department": department, "rate": rate, "runs": runs})
    for rows in index.values():
        rows.sort(key=lambda row: (-(row["rate"] or -1), -row["runs"], row["worker"]))
    payload = {"at": _now(), "skills": len(index),
               "workers": len({row["worker"] for rows in index.values() for row in rows})}
    (_dir(runtime) / "_experts.json").write_text(
        json.dumps({"summary": payload, "index": index}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return index


def find_expert(runtime, skill: str, *, exclude: list[str] | None = None,
                limit: int = 3) -> list[dict]:
    try:
        payload = json.loads((_dir(runtime) / "_experts.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = list((payload.get("index") or {}).get(skill) or [])
    excluded = set(exclude or [])
    return [row for row in rows if row["worker"] not in excluded][:limit]


def handoff(runtime, *, mission_id, from_worker, to_worker, reason, evidence_ok=False) -> dict:
    return _append_collective(runtime, {
        "at": _now(), "kind": "handoff", "mission_id": str(mission_id),
        "from": str(from_worker), "to": str(to_worker), "reason": str(reason)[:240],
        "verified": bool(evidence_ok)})


def peer_review(runtime, *, mission_id, reviewer, verdict, note, evidence_ok=False) -> dict:
    if verdict not in {"pass", "fail", "needs_work"}:
        raise ValueError("verdict must be pass/fail/needs_work")
    return _append_collective(runtime, {
        "at": _now(), "kind": "peer_review", "mission_id": str(mission_id),
        "reviewer": str(reviewer), "verdict": verdict, "note": str(note)[:300],
        "verified": bool(evidence_ok)})


def mentor_pairs(runtime, departments: list[dict]) -> list[dict]:
    pairs = []
    for dep in departments:
        department = str(dep.get("department_id") or "")
        scored = []
        for worker in dep.get("workers") or []:
            wid = str(worker.get("worker_id") or "")
            if not wid:
                continue
            try:
                profile = load(runtime, wid, department)
            except ValueError:
                continue
            meta = metacognition(profile)
            scored.append((wid, float(meta.get("confidence") or 0)))
        if len(scored) < 2:
            continue
        scored.sort(key=lambda item: item[1])
        pairs.append({"department": department, "mentor": scored[-1][0],
                      "mentee": scored[0][0], "mentor_confidence": scored[-1][1],
                      "mentee_confidence": scored[0][1]})
    (_dir(runtime) / "_mentors.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    return pairs


# --------------------------------------------------------------------------- #
# Uzun vadeli hafıza, meta-hafıza, paylaşılan bilgi, geri çağırma
# --------------------------------------------------------------------------- #

def _long_term(profile) -> dict:
    memory = profile.setdefault("memory", {})
    return memory.setdefault("long_term", {"by_plan": {}, "months": {}, "milestones": []})


def remember_long_term(profile, *, mission_id: str, plan_type: str, ok: bool,
                       department: str = "") -> dict:
    """Uzun vadeli gelişim: plan tipi ve ay bazında kümülatif, mission_id'li."""

    long_term = _long_term(profile)
    row = long_term["by_plan"].setdefault(
        plan_type, {"ok": 0, "fail": 0, "last_at": ""})
    row["ok" if ok else "fail"] += 1
    row["last_at"] = _now()
    month = time.strftime("%Y-%m")
    bucket = long_term["months"].setdefault(month, {"ok": 0, "fail": 0})
    bucket["ok" if ok else "fail"] += 1
    long_term["milestones"].append({
        "at": _now(), "mission_id": str(mission_id), "plan_type": str(plan_type),
        "ok": bool(ok), "department": str(department)})
    del long_term["milestones"][:-100]
    return row


def meta_note(profile, source: str, ok: bool) -> dict:
    """Meta-hafıza: bilgi kaynağının güvenilirliğini gözlenmiş sonuçla izler."""

    meta = profile.setdefault("meta_memory", {})
    row = meta.setdefault(str(source), {"ok": 0, "fail": 0, "last_at": ""})
    row["ok" if ok else "fail"] += 1
    row["last_at"] = _now()
    row["reliability"] = round(row["ok"] / max(1, row["ok"] + row["fail"]), 3)
    return row


def share_knowledge(runtime, *, department: str, statement: str, source: str,
                    mission_id: str = "", verified: bool = False) -> dict:
    """Departmanlar arası bilgi deposuna kayıt; doğrulanmışsa tekilleştirir."""

    record = {"at": _now(), "department": str(department),
              "statement": str(statement)[:400], "source": str(source),
              "mission_id": str(mission_id), "verified": bool(verified)}
    path = _dir(runtime) / "_shared.jsonl"
    if verified and path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("verified") and row.get("statement") == record["statement"]:
                return row
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def share_from_profile(runtime, profile, *, statement: str, source: str,
                       mission_id: str = "", verified: bool = False) -> dict:
    record = share_knowledge(runtime, department=str(profile.get("department") or ""),
                             statement=statement, source=source,
                             mission_id=mission_id, verified=verified)
    shared = profile["memory"].setdefault("shared", [])
    shared.append({key: record[key] for key in
                   ("at", "statement", "source", "mission_id", "verified")})
    del shared[:-40]
    return record


def _terms(text: str) -> set[str]:
    folded = (str(text or "").casefold()
              .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
              .replace("ü", "u").replace("ö", "o").replace("ç", "c"))
    return {word for word in re.findall(r"[a-z0-9]{3,}", folded)}


def _confidence(item: dict, kind: str) -> float:
    if kind == "semantic":
        return 1.0 if item.get("verified") else 0.4
    if kind == "episodic":
        return 0.9 if item.get("evidence_ok") else 0.3
    if kind == "shared":
        return 0.9 if item.get("verified") else 0.4
    if kind == "procedural":
        return float(item.get("rate") or 0.0)
    return 0.5


def recall(profile, query: str, *, limit: int = 5) -> list[dict]:
    """Kaynak + tarih + güven puanıyla hafıza geri çağırma."""

    wanted = _terms(query)
    hits: list[tuple[float, dict]] = []
    for kind in ("semantic", "episodic", "shared", "procedural"):
        for item in profile.get("memory", {}).get(kind) or []:
            text = item.get("statement") or item.get("summary") or item.get("plan_type") or ""
            overlap = len(wanted & _terms(text))
            if not overlap and wanted:
                continue
            confidence = _confidence(item, kind)
            score = round(overlap * confidence, 4) if wanted else confidence
            hits.append((score, {"kind": kind, "text": str(text)[:300],
                                 "source": item.get("source") or item.get("mission_id") or "",
                                 "at": item.get("at") or item.get("updated_at") or "",
                                 "confidence": confidence,
                                 "mission_id": item.get("mission_id") or ""}))
    hits.sort(key=lambda pair: (pair[0], pair[1]["at"]), reverse=True)
    return [row for _, row in hits[:max(1, int(limit))]]


def resolve_conflict(profile, *, existing: dict, candidate: dict) -> dict:
    """Çelişkide daha güvenilir kanıtı seçer; kaydı silmez, çelişkiyi saklar."""

    def score(item: dict) -> float:
        if "confidence" in item:
            return float(item["confidence"])
        return 1.0 if item.get("verified") else 0.4

    winner, loser = (candidate, existing) if score(candidate) >= score(existing) else (existing, candidate)
    record = {"at": _now(), "existing": existing, "candidate": candidate,
              "winner": winner, "reason": f"confidence {score(winner)} >= {score(loser)}"}
    conflicts = profile.setdefault("conflicts", [])
    conflicts.append(record)
    del conflicts[:-50]
    return record


# --------------------------------------------------------------------------- #
# Çok aşamalı planlama ve belirsizlik değerlendirmesi
# --------------------------------------------------------------------------- #

def build_plans(profile, *, goal: str, candidates: list[dict]) -> dict:
    """En az üç stratejiyi zorunlu alanlarla karşılaştırır; seçimi gerekçeler."""

    if len(candidates) < 3:
        raise ValueError("at least three candidate strategies are required")
    plans = []
    for index, item in enumerate(candidates):
        plan = {
            "name": str(item.get("name") or f"strateji-{index + 1}"),
            "goal": str(goal),
            "steps": [str(step)[:160] for step in item.get("steps") or []][:12],
            "tools": [str(tool) for tool in item.get("tools") or []][:8],
            "dependencies": [str(dep) for dep in item.get("dependencies") or []][:8],
            "expected_result": str(item.get("expected_result") or "")[:200],
            "estimated_cost_usd": round(float(item.get("estimated_cost_usd") or 0.0), 4),
            "risk": _clamp(item.get("risk", 0.5)),
            "success_probability": _clamp(item.get("success_probability", 0.5)),
            "verification": str(item.get("verification") or "bagimsiz QA"),
            "alternative": str(item.get("alternative") or ""),
        }
        evidence = float(item.get("evidence_score") or 0.5)
        plan["score"] = round(plan["success_probability"] * (1 - plan["risk"]) * 0.7
                              + _clamp(evidence) * 0.3, 4)
        plans.append(plan)
    plans.sort(key=lambda plan: plan["score"], reverse=True)
    chosen = plans[0]
    profile["goals"] = {
        "current": str(goal), "options": plans, "chosen": chosen["name"],
        "rationale": (f"{chosen['name']} seçildi: skor {chosen['score']} "
                      f"(başarı {chosen['success_probability']}, risk {chosen['risk']})"),
        "updated_at": _now()}
    return profile["goals"]


def assess_task(profile, *, task: str, required_skills: list[str] | None = None) -> dict:
    """Üstbiliş: yapabilir miyim, belirsizlik ne, kim daha uzman, QA gerekli mi?"""

    meta = metacognition(profile)
    samples = int(meta.get("samples") or 0)
    error_rate = float(meta.get("error_rate") or 0.0)
    confidence = float(meta.get("confidence") or 0.5)
    similar = [row for row in profile["memory"]["episodic"]
               if _terms(task) & _terms(row.get("summary") or "")]
    similar_success = (sum(1 for row in similar if row.get("outcome") == "completed")
                       / len(similar)) if similar else None
    if samples == 0:
        decision, reason = "research", "doğrulanmış deneyim yok; önce araştır"
    elif error_rate >= 0.5:
        decision, reason = "ask_help", "hata oranı yüksek; uzman desteği al"
    elif confidence < 0.55:
        decision, reason = "safe_test", "güven düşük; küçük güvenli test yap"
    elif error_rate >= 0.3:
        decision, reason = "verify_first", "geçmiş hatalar var; önce doğrula"
    else:
        decision, reason = "proceed", "benzer görevlerde kanıtlı başarı var"
    return {
        "task": str(task), "can_do": decision in {"proceed", "verify_first"},
        "samples": samples, "confidence": confidence, "error_rate": error_rate,
        "similar_tasks": len(similar), "similar_success": similar_success,
        "missing_information": ([] if samples else ["doğrulanmış görev geçmişi"]),
        "qa_required": decision != "proceed" or confidence < 0.8,
        "decision": decision, "reason": reason,
        "required_skills": list(required_skills or []),
    }


def summary(runtime) -> dict:
    rows = []
    for path in _dir(runtime).glob("*.json"):
        if path.name.startswith(("_", ".")):
            continue
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(profile, dict) or "memory" not in profile:
            continue
        rows.append({"worker": profile.get("worker_id"),
                     "episodic": len(profile["memory"]["episodic"]),
                     "semantic": len(profile["memory"]["semantic"]),
                     "procedural": len(profile["memory"]["procedural"]),
                     "evidence": profile.get("evidence", {}).get("status"),
                     "confidence": profile["metacognition"].get("confidence")})
    return {"profiles": len(rows),
            "with_episodic": sum(1 for row in rows if row["episodic"]),
            "with_verified_evidence": sum(1 for row in rows if row["evidence"] == "verified"),
            "workers": rows}
