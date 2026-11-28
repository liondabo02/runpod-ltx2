"""AHOS çekim planlayıcı (saf Python): beat_sheet + voice_manifest + bible -> render planı JSON."""
import json, os, re
import shot_motion as sm
import props2d
import staging
import setpieces2d
import continuity
import action_staging
import shot_cuts
try:
    import pointing                       # gösterme jesti bloklaması (çizim modülü gerektirir)
except ImportError:
    pointing = None
try:
    import puppet2d as _pp
except ImportError:
    _pp = None
try:
    import mood_engine
except ImportError:
    mood_engine = None

DEFAULT_HEIGHT_M = 1.1          # yalnız puppet2d yüklenemediğinde; puppet2d.DEFAULT_HEIGHT_M ile eşitliği testle korunur

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


def spec_height(assets_dir, cid):
    """Çizim modülü (Pillow) yokken boy: spec'ten, yoksa ortak varsayılan. Çizim modülü varken kaynak designs_for'dur."""
    spec_p = os.path.join(assets_dir, f"{cid}.spec.json")
    spec = json.load(open(spec_p, encoding="utf-8")) if os.path.exists(spec_p) else {}
    return float(spec.get("height_m", getattr(_pp, "DEFAULT_HEIGHT_M", DEFAULT_HEIGHT_M)))


def plan(episode_dir, bible, assets_dir, t0, t1, fps=None, size=(1280, 720)):
    fps = int(fps or os.environ.get("AHOS_FPS", "12"))
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    vm_path = os.path.join(episode_dir, "voice_manifest.json")
    items = assign_offsets(json.load(open(vm_path, encoding="utf-8"))["items"]) if os.path.exists(vm_path) else []
    names = {c["id"]: c.get("name", c["id"]) for c in bible["characters"]}
    out = {"fps": fps, "width": size[0], "height": size[1], "t0": t0, "t1": t1, "characters": {}, "beats": [],
           "total_s": float(sheet["beats"][-1]["t_end"]) if sheet.get("beats") else 480.0}
    des_ = {}
    if _pp is not None:                                      # boy ve el değiştirme erişimi: çizimle AYNI ölçü ve aynı tasarım kaynağı (planlayıcı ayrı tahmin yapmaz)
        try:
            des_ = _pp.designs_for(bible, assets_dir)
        except Exception:
            des_ = {}
    for ch in bible["characters"]:
        glb = os.path.join(assets_dir, "character-model", f"{ch['id']}-model.glb")
        h = des_[ch["id"]]["height"] if ch["id"] in des_ else spec_height(assets_dir, ch["id"])
        out["characters"][ch["id"]] = {"glb": glb, "height": h, "name": names[ch["id"]]}
    reach_fn_ = (lambda a, xa, b, xb: _pp.handoff_reach_ratio(des_[a], xa, des_[b], xb)) if _pp is not None and des_ else None
    world_x_ = {}; world_obj_ = {}; prev_meta_ = None; prev_beat_ = None; every_ = []       # birikmiş dünya durumu: kadraj dışındaki oyuncu/nesne de korunur
    locs_ = setpieces2d.load_locations(os.path.dirname(os.path.abspath(assets_dir)))        # proje verisi: mekân -> dekor parçaları (motor mekân adlarını bilmez)
    for bi, b in enumerate(sheet["beats"]):
        ts, te = float(b["t_start"]), float(b["t_end"])
        in_win = te > t0 and ts < t1                                    # pencere öncesi planlar da hesaplanır (durum taşınır), çıktıya yazılmaz
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
        trans_ = continuity.transition_kind(prev_meta_, {"scene_id": b.get("scene_id"), "loc": b.get("location"), "transition": b.get("transition")})
        if trans_ in continuity.FREE:
            world_x_, world_obj_ = {}, {}
        continuity.carry_starts(mot, world_x_, trans_)                  # sürekli geçişte başlangıç = önceki bitiş (ışınlanma yok)
        prev_meta_ = {"scene_id": b.get("scene_id"), "loc": b.get("location")}
        ch_ = b.get("choreo") or {}                      # yönetmen koreografisi: açık hareket/hedef/nesne izi/bakış (planlayıcı tahminini ezer)
        for c_, spec_ in (ch_.get("motion") or {}).items():
            if c_ in mot:
                mot[c_] = {"kind": spec_.get("kind", mot[c_]["kind"]), "x0": float(spec_.get("x0", mot[c_]["x0"])),
                           "x1": float(spec_.get("x1", spec_.get("x0", mot[c_]["x1"]))), "seed": mot[c_]["seed"]}
                if mot[c_]["kind"] not in continuity.MOVING:
                    mot[c_]["x1"] = mot[c_]["x0"]                       # duran eylem yer değiştirmez (çizim yalnız x0 kullanır)
        spec_ = locs_.get(b.get("location") or "", {}); pieces_ = setpieces2d.pieces_of(spec_)
        tg_, sk_ = setpieces2d.anchors_for(pieces_)
        gaps_ = [f"mekân '{b.get('location')}': dekor parçası motor kataloğunda yok: {n}" for n in setpieces2d.unknown_pieces(spec_)]
        if b.get("location") and not spec_:
            gaps_.append(f"mekân '{b.get('location')}': proje verisinde (locations.json) dekor tanımı yok; arka plan dışında çizilecek bir şey yok")
        heights_ = {c: out["characters"][c]["height"] for c in cast if c in out["characters"]}
        listed_ = list(ch_.get("objects", []))
        carried_, obj_gaps_ = continuity.carry_objects(world_obj_, listed_, cast, te - ts, tg_)     # anılmayan nesne kaybolmaz
        objs_ = listed_ + carried_; gaps_ += obj_gaps_
        gaze_ = ch_.get("gaze", {}); react_ = ch_.get("react", {})
        sm.mark_halt(mot, react_)                                       # yürüyüşü kesen tepki: çözücüler de frenlenen konumu görür
        stg_notes = staging.resolve(mot, objs_, heights_, tg_, prev_x=world_x_, reach_fn=reach_fn_, dur=te - ts)
        stg_notes += continuity.reconcile(mot, world_x_, trans_, heights_, te - ts, objs_, react_)  # koreografi işareti ışınlanma yaratamaz
        blk_ = action_staging.resolve(mot, objs_, heights_, tg_, world_x_, trans_, te - ts, react_)  # seyirci içinden geçmesin / atış koridorunda durmasın
        stg_notes = action_staging.merge(stg_notes, blk_, mot, world_x_, trans_)
        if des_:                                                       # eşit/yakın boyda yüz örtmesini bloklama kendisi ayırır (çizilen tasarım boylarıyla)
            sep_ = action_staging.separate(mot, objs_, des_, world_x_, trans_, te - ts, react_,
                                           {n_["actor"] for n_ in stg_notes if n_.get("kind") == "conflict"})
            stg_notes = action_staging.merge(stg_notes, sep_, mot, world_x_, trans_)
        if des_ and pointing is not None and ch_.get("points"):         # gösteren elin önü açık olsun (jest zamanı replikten de gelebilir)
            view_ = {"t_start": ts, "t_end": te, "cast": cast, "lines": lines, "motion": mot, "targets": tg_,
                     "choreo": {"objects": objs_, "points": ch_["points"]}}
            pt_ = pointing.clear(view_, des_, world_x_, trans_, react_,
                                 {n_["actor"] for n_ in stg_notes if n_.get("kind") == "conflict"})
            stg_notes = action_staging.merge(stg_notes, pt_, mot, world_x_, trans_)
        sm.mark_halt(mot, react_)                                       # çözücülerin yeniden kurduğu hareketlerde de aynı fren
        for c_, m_ in mot.items():                                      # sonraki plana süreklilik: plan sonunda ÇİZİLEN konum
            m_["x_end"] = round(sm.exit_x(m_, te - ts, heights_[c_], react_.get(c_)), 4)
            world_x_[c_] = m_["x_end"]
        continuity.update_objects(world_obj_, objs_, tg_)
        cam_text = (b.get("camera") or "").lower()
        preset = "close" if re.search(r"yakın|close|detay", cam_text) else "medium" if re.search(r"orta|omuz|medium", cam_text) \
            else "wide" if re.search(r"genel|geniş|wide", cam_text) else None
        if preset is None:  # kamera belirtilmemiş: genel plan ağırlıklı döngü (gövdeler kadrajda kalsın)
            preset = ("wide", "medium", "wide", "close")[bi % 4]
        # sinematograf çeşitliliği: konuşma varsa ve hep 'genel' ise araya orta/yakın plan koy
        if preset == "wide" and lines and bi % 3 != 0:
            preset = "medium" if bi % 3 == 1 else "close"
        focus = lines[0]["char"] if lines else (cast[0] if cast else None)
        out["beats"].append({"i": bi, "t_start": ts, "t_end": te, "scene": b.get("scene_kind") or scene_type(b.get("location"), bible.get("locations")),
                             "cast": cast, "motion": mot, "lines": lines, "camera": preset, "focus": focus,
                             "loc": b.get("location"), "light": b.get("light_time", ""), "shot_id": b.get("shot_id"),
                             "mood": (mood_engine.mood_for(b.get("action", ""), (b.get("emotion") or {}).get("valence")) if mood_engine else "neutral"),
                             "staging_notes": stg_notes, "pieces": pieces_, "targets": tg_, "sinks": sorted(sk_), "capability_gaps": gaps_, "transition_kind": trans_, "choreo": {"objects": objs_, "gaze": gaze_, "react": react_, "points": ch_.get("points", [])},
                             "icons": (ch_.get("icons", []) if ch_ else _icons(b.get("action", ""))), "scene_id": b.get("scene_id"),
                             "first_of_scene": bi == 0 or sheet["beats"][bi - 1].get("scene_id") != b.get("scene_id"),
                             "props": ([] if ch_ else props2d.extract(str(b.get("action", "")) + " " + str(b.get("camera", "")))),
                             "fx": props2d.fx_kinds([m_["kind"] for m_ in mot.values()])})
        if out["beats"][-1]["props"] and not lines and bi % 3 == 2 and preset != "close":  # nesne ara planı (kesme)
            out["beats"][-1]["camera"] = "insert"
        shot_cuts.link(prev_beat_, out["beats"][-1])                  # kurgu sürekliliği pencere öncesi vuruşlardan da taşınır
        if _pp is not None:                                            # tutan el sürekliliği: elde gelen nesne vuruş sınırında öbür ele ışınlanmaz
            import render2d as _r2
            _r2.hand_link(prev_beat_, out["beats"][-1])
        prev_beat_ = out["beats"][-1]
        every_.append((prev_beat_, in_win))
        if not in_win:
            out["beats"].pop()
        if ts >= t1 and not (len(every_) > 1 and shot_cuts.continues(every_[-2][0], prev_beat_)):
            break                                                       # pencere sonrası yalnız kesintisiz süren komşular okunur
    out["context"] = shot_cuts.window_context(every_)       # pencere kenarında süren çekimin komşuları: parça parça üretimde kadraj aynı kalır
    return out
