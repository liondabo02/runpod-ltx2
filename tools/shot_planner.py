"""AHOS çekim planlayıcı (saf Python): beat_sheet + voice_manifest + bible -> render planı JSON."""
import json, os, re
import shot_motion as sm
import props2d
try:
    import mood_engine
except ImportError:
    mood_engine = None

SCENE_RULES = [("stage", r"sahne|stand-?up|tiyatro|stage|mikrofon|konser"), ("room", r"^home_|mutfak|salon|giriş koridoru|ev giriş"), ("water", r"göl|gol\b|nehir|dere|deniz|su kenar|lake|river|sea|pond"), ("path", r"koridor|yol\b|patika|rüzgar|ruzgar|corridor|path|road|tepe|hill"), ("roof", r"çatı|cati|roof|tavan"), ("room", r"oda|ev\b|mutfak|salon|room|house|kitchen|sınıf"),
               ("village", r"köy|koy\b|mahalle|sokak|meydan|çarşı|carsi|pazar|village|street|square|market"),
               ("garden", r"bahçe|bahce|park|orman|çayır|garden|forest|meadow")]


def scene_type(loc_id, locations):
    desc = loc_id or ""
    for l in locations or []:
        if l.get("id") == loc_id:
            desc += " " + str(l.get("name", "")) + " " + str(l.get("description", ""))
    for typ, pat in SCENE_RULES:
        if re.search(pat, desc, re.I):
            return typ
    return "garden"


def assign_offsets(items):
    """Aynı vuruştaki satırlar art arda konuşur (üst üste binmez). start_s: vuruş başından saniye."""
    cur = {}
    for it in items:
        b = it["beat"]
        if "start_s" not in it:
            it["start_s"] = round(cur.get(b, 0.2), 2)
        cur[b] = it["start_s"] + float(it["duration_s"]) + 0.3
    return items


def load_cues(episode_dir, item):
    p = item.get("visemes")
    if not p:
        return []
    path = os.path.join(episode_dir, p.replace("\\", "/"))
    if not os.path.exists(path):
        return []
    try:
        raw = json.load(open(path, encoding="utf-8")).get("mouthCues", [])
    except Exception:
        return []
    return [[c["start"], c["end"], sm.VISEME_OPEN.get(c["value"], 0.3), c["value"]] for c in raw]


def _icons(action):
    try:
        import fx_layer
        return fx_layer.kinds_for(action)
    except ImportError:
        return []


def plan(episode_dir, bible, assets_dir, t0, t1, fps=None, size=(1280, 720)):
    fps = int(fps or os.environ.get("AHOS_FPS", "12"))
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    vm_path = os.path.join(episode_dir, "voice_manifest.json")
    items = assign_offsets(json.load(open(vm_path, encoding="utf-8"))["items"]) if os.path.exists(vm_path) else []
    names = {c["id"]: c.get("name", c["id"]) for c in bible["characters"]}
    out = {"fps": fps, "width": size[0], "height": size[1], "t0": t0, "t1": t1, "characters": {}, "beats": [],
           "total_s": float(sheet["beats"][-1]["t_end"]) if sheet.get("beats") else 480.0}
    for ch in bible["characters"]:
        glb = os.path.join(assets_dir, "character-model", f"{ch['id']}-model.glb")
        spec_p = os.path.join(assets_dir, f"{ch['id']}.spec.json")
        h = json.load(open(spec_p, encoding="utf-8")).get("height_m", 1.2) if os.path.exists(spec_p) else 1.2
        out["characters"][ch["id"]] = {"glb": glb, "height": h, "name": names[ch["id"]]}
    for bi, b in enumerate(sheet["beats"]):
        ts, te = float(b["t_start"]), float(b["t_end"])
        if te <= t0 or ts >= t1:
            continue
        cast = [c for c in b.get("characters", []) if c in out["characters"]]
        lines = [{"char": it["char"], "start": ts + it["start_s"], "end": ts + it["start_s"] + float(it["duration_s"]),
                  "cues": load_cues(episode_dir, it), "mood": mood_engine.mood_for(it.get("text")) if mood_engine else "neutral"}
                 for it in items if it["beat"] == bi and it["char"] in out["characters"]]
        for l in lines:
            if l["char"] not in cast:
                cast.append(l["char"])
        sl = sm.slots(len(cast))
        mot = {}
        for i, c in enumerate(cast):
            seed = bi * 3 + i
            kind = sm.motion_for(c, b.get("action", ""), names.get(c), seed)
            if kind == "idle" and not lines:   # sessiz vuruşta karakterler durmasın: dönüşümlü yürü/bak
                kind = "walk" if (seed + bi) % 2 == 0 else "look"
            if kind == "idle" and i > 0 and lines:
                kind = "look" if seed % 2 else "idle"
            mot[c] = {"kind": kind, "x0": sl[i], "x1": sm.move_target(kind, sl[i], seed), "seed": seed}
        cam_text = (b.get("camera") or "").lower()
        preset = "close" if re.search(r"yakın|close|detay", cam_text) else "medium" if re.search(r"orta|omuz|medium", cam_text) \
            else "wide" if re.search(r"genel|geniş|wide", cam_text) else None
        if preset is None:  # kamera belirtilmemiş: genel plan ağırlıklı döngü (gövdeler kadrajda kalsın)
            preset = ("wide", "medium", "wide", "close")[bi % 4]
        # sinematograf çeşitliliği: konuşma varsa ve hep 'genel' ise araya orta/yakın plan koy
        if preset == "wide" and lines and bi % 3 != 0:
            preset = "medium" if bi % 3 == 1 else "close"
        focus = lines[0]["char"] if lines else (cast[0] if cast else None)
        out["beats"].append({"i": bi, "t_start": ts, "t_end": te, "scene": scene_type(b.get("location"), bible.get("locations")),
                             "cast": cast, "motion": mot, "lines": lines, "camera": preset, "focus": focus,
                             "loc": b.get("location"), "light": b.get("light_time", ""), "shot_id": b.get("shot_id"),
                             "mood": (mood_engine.mood_for(b.get("action", ""), (b.get("emotion") or {}).get("valence")) if mood_engine else "neutral"),
                             "icons": _icons(b.get("action", "")), "scene_id": b.get("scene_id"),
                             "first_of_scene": bi == 0 or sheet["beats"][bi - 1].get("scene_id") != b.get("scene_id"),
                             "props": props2d.extract(str(b.get("action", "")) + " " + str(b.get("camera", ""))),
                             "fx": props2d.fx_kinds([m_["kind"] for m_ in mot.values()])})
        if out["beats"][-1]["props"] and not lines and bi % 3 == 2 and preset != "close":  # nesne ara planı (kesme)
            out["beats"][-1]["camera"] = "insert"
    return out
