#!/usr/bin/env python3
"""AHOS Dizi Hafızası (diziden bağımsız): bölümler arası tutarlılık için kalıcı 'kanon'.
series/<id>/memory.json: karakter/mekân kilitleri (görünüş+ses imzası), bölüm kayıtları (olaylar, nesneler, mekânlar,
çözülmemiş konular), ilişkiler. Hafıza YALNIZ olgu tutar; yaratıcı kararı sahip verir. Kod değiştirmez."""
import hashlib, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import props2d  # noqa: E402


def _path(series_dir):
    return os.path.join(series_dir, "memory.json")


def load(series_dir):
    try:
        return json.load(open(_path(series_dir), encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"version": 1, "characters": {}, "locations": {}, "episodes": [], "threads": [], "objects": {}}


def save(series_dir, mem):
    os.makedirs(series_dir, exist_ok=True)
    json.dump(mem, open(_path(series_dir), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _sig(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def lock_canon(series_dir, bible, assets_dir=None):
    """İlk kez kilitler; sonra değişirse 'DRIFT' olarak raporlanır (sessizce değişmez). Dönen: değişiklik listesi."""
    mem = load(series_dir); drift = []
    assets_dir = assets_dir or os.path.join(series_dir, "assets")
    for c in bible.get("characters", []):
        spec = {}
        sp = os.path.join(assets_dir, c["id"] + ".spec.json")
        if os.path.exists(sp):
            try:
                spec = json.load(open(sp, encoding="utf-8"))
            except ValueError:
                pass
        look = {"name": c.get("name"), "age": c.get("age"), "appearance": c.get("appearance") or c.get("look"),
                "voice_hint": c.get("voice_hint"), "spec": spec}
        sg = _sig(look); cur = mem["characters"].get(c["id"])
        if not cur:
            mem["characters"][c["id"]] = {"sig": sg, "look": look, "locked_at": time.strftime("%Y-%m-%d")}
        elif cur["sig"] != sg:
            drift.append({"kind": "character", "id": c["id"], "was": cur["sig"], "now": sg})
    for l in bible.get("locations", []):
        look = {"name": l.get("name"), "description": l.get("description"), "light_by_time": l.get("light_by_time")}
        sg = _sig(look); cur = mem["locations"].get(l["id"])
        if not cur:
            mem["locations"][l["id"]] = {"sig": sg, "look": look}
        elif cur["sig"] != sg:
            drift.append({"kind": "location", "id": l["id"], "was": cur["sig"], "now": sg})
    save(series_dir, mem)
    return drift


def approve_drift(series_dir, bible):
    """Sahip değişikliği bilerek onaylarsa kilidi yeniler."""
    mem = load(series_dir); mem["characters"] = {}; mem["locations"] = {}; save(series_dir, mem)
    return lock_canon(series_dir, bible)


def record_episode(series_dir, eid, sheet):
    """Bölümden olguları çıkarır (kodla, LLM'siz): mekânlar, objeler, konuşanlar, son durum, çözülmemiş sorular."""
    mem = load(series_dir)
    beats = sheet.get("beats", [])
    locs, objs, speakers, text = [], [], {}, []
    for b in beats:
        if b.get("location") and b["location"] not in locs:
            locs.append(b["location"])
        a = str(b.get("action", "")); text.append(a)
        for k in props2d.extract(a, 5):
            if k not in objs:
                objs.append(k)
        for part in str(b.get("dialogue", "")).split("|"):
            if ":" in part:
                who = part.split(":", 1)[0].strip()
                speakers[who] = speakers.get(who, 0) + 1
    threads = [str(b.get("action", ""))[:140] for b in beats[-3:] if "?" in str(b.get("dialogue", "")) or "gizem" in str(b.get("action", "")).lower()]
    rec = {"id": eid, "title": sheet.get("title"), "logline": sheet.get("logline"), "locations": locs, "objects": objs,
           "speakers": speakers, "ending": str(beats[-1].get("action", ""))[:200] if beats else "", "open_threads": threads,
           "duration_s": float(beats[-1]["t_end"]) if beats else 0, "recorded": time.strftime("%Y-%m-%d %H:%M")}
    mem["episodes"] = [e for e in mem["episodes"] if e["id"] != eid] + [rec]
    for o in objs:
        mem["objects"].setdefault(o, []).append(eid)
    mem["threads"] = (mem["threads"] + [{"ep": eid, "t": t} for t in threads])[-12:]
    save(series_dir, mem)
    return rec


def context_block(series_dir, last_n=4):
    """Yazarlara verilecek kısa süreklilik bloğu."""
    mem = load(series_dir)
    if not mem["episodes"]:
        return ""
    L = ["SÜREKLİLİK (değiştirme, devam ettir):"]
    for e in mem["episodes"][-last_n:]:
        L.append(f"- {e['id']} '{e.get('title')}': {e.get('logline')} | mekânlar: {', '.join(e['locations'])} | objeler: {', '.join(e['objects'])} | sonu: {e['ending'][:120]}")
    if mem["threads"]:
        L.append("Çözülmemiş konular: " + " ; ".join(t["t"][:80] for t in mem["threads"][-4:]))
    L.append("Karakter görünüşü, sesi ve kişiliği sabit kalır; yeni karakteri yalnız senaryo getirirse ekle.")
    return "\n".join(L)
