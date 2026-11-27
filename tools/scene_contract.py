"""AHOS ortak sahne sözleşmesi (sürümlü). Kamera, süreklilik, animasyon, ses, QA aynı kimlik ve durum verisini okur.
Sözleşme proje/bölüm/sahne/plan/olay kimlikleri, karakter+varlık sürümleri, aktör/nesne giriş-çıkış durumu,
diyalog+dil, kamera niyeti, ses olayları, gereken yetenekler ve üretim/onay bağlantılarını taşır.
Motor hiçbir projeye özgü ad bilmez; veri proje dosyalarından gelir. Eski veri: upgrade()/from_beat_sheet()."""
import hashlib, json
import continuity
import shot_motion as sm

SCHEMA = "ahos.scene_contract"
VERSION = 1
ENGINES = ("script", "staging", "camera", "animation", "object_state", "audio", "localisation", "render", "qa")


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def _dialogue(raw):
    out = []
    for part in str(raw or "").split("|"):
        if ":" in part:
            c, t = part.split(":", 1)
            out.append((c.strip(), t.strip()))
    return out


def from_beat_sheet(sheet, plan=None, *, project_id, episode_id, asset_versions=None, languages=("tr",)):
    """sheet: beat_sheet.json; plan: shot_planner.plan çıktısı (varsa konumlar oradan)."""
    pb = {b["i"]: b for b in (plan or {}).get("beats", [])}
    shots, gaps = [], []
    for i, b in enumerate(sheet["beats"]):
        pl = pb.get(i); ch = b.get("choreo") or {}
        scene = b.get("scene_id") or "SC00"; sid = b.get("shot_id") or f"{scene.lower()}_s{i:03d}"
        cast = list(pl["cast"]) if pl else list(b.get("characters", []))
        motion = (pl or {}).get("motion") or {c: {"x0": v.get("x0"), "x1": v.get("x1", v.get("x0"))} for c, v in (ch.get("motion") or {}).items()}
        ents = {c: {"x": (sm.entry_x(m) if m.get("x0") is not None else None)} for c, m in motion.items()}       # plan başında çizilen konum
        exs = {c: {"x": next((v for v in (m.get("x_end"), m.get("x1"), m.get("x0")) if v is not None), None)} for c, m in motion.items()}
        eo, xo, events = {}, {}, []
        objects = ((pl or {}).get("choreo") or {}).get("objects")            # planlayıcının (taşınan nesneler dahil) izleri
        objects = ch.get("objects", []) if objects is None else objects
        targets = (pl or {}).get("targets") or {}; dur = float(b["t_end"]) - float(b["t_start"])
        for ob in objects:
            n = continuity.object_name(ob); tr = ob.get("track") or []
            if n in eo:
                gaps.append({"shot": sid, "engine": "object_state", "rule": "DUP_OBJECT", "why": f"aynı kimlikte iki nesne izi: {n} (ayrı 'id' verin)"})
            if tr and tr[-1].get("t", 0) > dur + 0.05:
                gaps.append({"shot": sid, "engine": "object_state", "rule": "OBJECT_EVENT_OUTSIDE", "why": f"{n}: iz {tr[-1]['t']} sn'de bitiyor, plan {dur:.2f} sn; plan sonu durumu belirsiz"})
            eo[n] = continuity.object_point(tr, "first", targets); xo[n] = continuity.object_point(tr, "last", targets)
            for k, p in enumerate(tr):
                if p.get("holder") != (tr[k - 1].get("holder") if k else p.get("holder")):
                    events.append({"id": f"{sid}.o{len(events):02d}", "kind": "object", "t": p.get("t"), "object": n, "holder": p.get("holder")})
        lines = (pl or {}).get("lines") or []
        for k, (c, text) in enumerate(_dialogue(b.get("dialogue"))):
            ln = next((l for l in lines if l["char"] == c), None)
            for lang in languages:
                events.append({"id": f"{sid}.d{k:02d}.{lang}", "kind": "dialogue", "char": c, "lang": lang, "text": text if lang == languages[0] else None,
                               "t_start": ln["start"] if ln else None, "t_end": ln["end"] if ln else None})
        if b.get("sound"):
            events.append({"id": f"{sid}.s00", "kind": "sfx", "text": b["sound"], "t": b["t_start"]})
        caps = sorted({f"piece:{p[0] if isinstance(p, (list, tuple)) else p}" for p in (pl or {}).get("pieces", [])})
        sg = list((pl or {}).get("capability_gaps", []))
        gaps += [{"shot": sid, "engine": "render", "why": g} for g in sg]
        gaps += [{"shot": sid, "engine": "staging", "rule": "STAGING_CONFLICT", "why": f"çelişki: {n.get('rule')} {n.get('actor')}: {n.get('why')}"} for n in (pl or {}).get("staging_notes", []) if n.get("kind") == "conflict"]
        shots.append({"shot_id": sid, "scene_id": scene, "index": i, "t_start": float(b["t_start"]), "t_end": float(b["t_end"]), "loc": b.get("location"),
                      "transition": b.get("transition"), "cast": cast, "entry": {"actors": ents, "objects": eo}, "exit": {"actors": exs, "objects": xo},
                      "camera_intent": {"preset": (pl or {}).get("camera") or b.get("camera"), "focus": (pl or {}).get("focus"), "targets": [t for t in (ch.get("gaze") or {}).values()]},
                      "events": events, "requires": caps, "capability_gaps": sg,
                      "refs": {"render": None, "audio": None, "qa": None}})
    for s in shots:
        s["events"] = sorted(s["events"], key=lambda e: e["id"])
    errs = continuity.check(shots)
    return {"schema": SCHEMA, "version": VERSION, "project_id": project_id, "episode_id": episode_id, "languages": list(languages),
            "versions": {"characters": dict(asset_versions or {}), "source_sheet": _hash(sheet)}, "shots": shots,
            "problems": errs, "gaps": gaps}


def validate(c):
    """Sorun listesi [{rule, engine, shot, why}]; boş değilse ilgili motor sorumludur."""
    p = []
    if c.get("schema") != SCHEMA:
        return [{"rule": "SCHEMA", "engine": "script", "shot": None, "why": "şema adı yok/yanlış; upgrade() kullan"}]
    if c.get("version", 0) > VERSION:
        return [{"rule": "VERSION", "engine": "script", "shot": None, "why": f"sözleşme sürümü {c['version']} bu motordan yeni ({VERSION})"}]
    seen, last = set(), None
    for s in c["shots"]:
        if s["shot_id"] in seen:
            p.append({"rule": "DUP_ID", "engine": "script", "shot": s["shot_id"], "why": "plan kimliği tekrarlı"})
        seen.add(s["shot_id"])
        if s["t_end"] <= s["t_start"]:
            p.append({"rule": "TIME", "engine": "script", "shot": s["shot_id"], "why": "süre <= 0"})
        if last is not None and s["t_start"] < last - 1e-6:
            p.append({"rule": "OVERLAP", "engine": "script", "shot": s["shot_id"], "why": "önceki planla zaman çakışması"})
        last = s["t_end"]
        ids = [e["id"] for e in s["events"]]
        if len(ids) != len(set(ids)):
            p.append({"rule": "DUP_EVENT", "engine": "script", "shot": s["shot_id"], "why": "olay kimliği tekrarlı"})
        for e in s["events"]:
            if e["kind"] == "dialogue" and e.get("lang") not in c["languages"]:
                p.append({"rule": "LANG", "engine": "localisation", "shot": s["shot_id"], "why": f"{e['id']}: dil sözleşmede yok"})
    p += [{"rule": g_.get("rule", "GAP"), "engine": g_["engine"], "shot": g_["shot"], "why": g_["why"]} for g_ in c.get("gaps", [])]
    p += [{"rule": e["rule"], "engine": e["engine"], "shot": e["shot"], "why": e["why"]} for e in continuity.check(c["shots"])]
    return p


def upgrade(obj):
    """Eski sürümleri bozmadan yükselt. v0: şemasız {'shots':[...]} -> v1 (eksik alanlar boş doldurulur)."""
    if obj.get("schema") == SCHEMA:
        return obj
    if "shots" in obj and "beats" not in obj:
        o = dict(obj); o.update({"schema": SCHEMA, "version": VERSION, "languages": o.get("languages", ["tr"]), "versions": o.get("versions", {}), "problems": [], "gaps": o.get("gaps", [])})
        for s in o["shots"]:
            s.setdefault("events", []); s.setdefault("requires", []); s.setdefault("capability_gaps", []); s.setdefault("refs", {})
            s.setdefault("entry", {"actors": {}, "objects": {}}); s.setdefault("exit", {"actors": {}, "objects": {}})
        return o
    raise ValueError("eski beat_sheet doğrudan yükseltilemez: from_beat_sheet(sheet, plan, project_id=, episode_id=) kullan")
