"""AHOS planlar arası süreklilik (genel motor kuralı; proje verisi bilmez).
Geçiş türleri (bir planın BAŞINDAKİ sınır):
  continuous / cut : dünya durumu sürer (kamera kesmesi aktörü ışınlamaz)
  time_skip        : açık anlatısal zaman atlaması (konum değişimine izin verir)
  scene_change     : sahne/mekân değişti (çıkarım; izin verir)
Işınlanma = bu iki serbest türün dışında konum/nesne sahibi sıçraması -> reddedilir (TELEPORT / OBJECT_JUMP).
DÜNYA DURUMU birikimlidir: bir planda ekranda olmayan aktör/nesne son durumunu korur; serbest geçiş dünyayı sıfırlar."""
import copy
import object_state
import shot_motion as sm

FREE = ("time_skip", "scene_change")
TOL_M = 0.15            # aynı dünya durumu sayılan konum farkı (metre)
MIN_SEP = 0.6           # iki aktörün en az aralığı (metre)
XLIM = 1.9
SNAP_M = 0.02           # bundan küçük fark: işaret doğrudan önceki bitişe çekilir (adım atılmaz)
MOVING = ("walk", "run", "carry")
VMAX = {"walk": 1.5, "carry": 1.2, "run": 3.0}      # m/sn, yetişkin üst sınırı (boya göre ölçeklenir)
ACC_S = 0.22            # yürüyüşün hazırlık payı (sn)


def object_name(ob):
    """Nesne kimliği: 'id' varsa o (aynı türden iki nesne), yoksa 'prop'."""
    return ob.get("id") or ob.get("prop", "obj")


def object_point(track, which, targets=None):
    """İzin ilk/son anahtarındaki durum: {'holder','at','pos','hidden'}; pos = dünya koordinatı (hedef adı çözülebiliyorsa)."""
    pts = [p for p in (track or []) if isinstance(p, dict)]
    if not pts:
        return None
    p = pts[0] if which == "first" else pts[-1]
    at = p.get("at")
    pos = (targets or {}).get(at) if isinstance(at, str) else at
    return {"holder": p.get("holder"), "at": at, "pos": list(pos) if pos is not None else None, "hidden": bool(p.get("hide"))}


def carry_objects(world, listed, cast, dur, targets=None):
    """Sürekli geçişte planın anmadığı nesneler kaybolmaz: son durumlarıyla iz üretilir (tutan oyuncu kadrajdaysa elinde; yerdeyse yerinde).
    world: {ad: {'holder','at','pos','hidden','prop','scale','surface'}}. Dönüş: (eklenecek izler, açıklar)."""
    have = {object_name(o) for o in listed}; add, gaps = [], []
    for name, st in sorted(world.items()):
        if name in have or st.get("hidden"):
            continue
        if st.get("holder"):
            if st["holder"] not in cast:
                continue                                              # tutan kadraj dışında: nesne onunla birlikte (dünya durumunda kalır)
            key = {"holder": st["holder"]}
        else:
            at = st.get("at")
            if isinstance(at, str) and at not in (targets or {}):
                gaps.append(f"nesne '{name}' önceki planda '{at}' hedefindeydi; bu planın mekân verisinde o hedef yok")
                continue
            key = {"at": at}
            if st.get("surface"):
                key["surface"] = st["surface"]
        ob = {"prop": st["prop"], "id": name, "carried": True, "track": [dict(key, t=0), dict(key, t=dur)]}
        if st.get("scale") is not None:
            ob["scale"] = st["scale"]
        add.append(ob)
    return add, gaps


def update_objects(world, objects, targets=None):
    """Plan sonunda nesne dünya durumunu günceller."""
    for ob in objects:
        end = object_point(ob.get("track"), "last", targets)
        if end is None:
            continue
        end.update(prop=ob.get("prop", "obj"), scale=ob.get("scale"), surface=ob["track"][-1].get("surface"))
        world[object_name(ob)] = end


def contact_deadline(objects, actor):
    """Bu aktörün planda yerinde olması gereken en erken an (sn) ve nedeni; teması yoksa (None, None)."""
    best = (None, None)
    for ob in objects or []:
        for e in object_state.events(ob.get("track") or []):
            if actor not in (e["by"], e.get("to")):
                continue
            if e["type"] == "handoff":
                d = e["t_start"]
            elif e["type"] == "pickup":
                d = max(e["t_start"], e["t"] - 0.6)
            else:
                d = max(0.0, e["t_start"] - 0.45)
            if best[0] is None or d < best[0]:
                best = (d, e["type"])
    return best


def reconcile(motion, prev_end, kind, heights, dur, objects=None, react=None):
    """Sürekli geçişte her aktör önceki planın bittiği yerden başlar. Senaryonun/koreografinin istediği işaret KORUNUR:
      hareketli eylem (walk/run/carry): yol önceki bitişten aynı hedefe gider;
      duran eylem: aktör önce işarete yürür ('approach'), eylemi orada yapar.
    Temasa/tepkiye ya da plan süresine yetişemiyorsa 'conflict' notu döner (sessizce ışınlanmaz). motion yerinde değişir."""
    notes = []
    if kind in FREE or not prev_end:
        return notes
    shared = sorted(c for c in motion if c in prev_end)
    for c, m in motion.items():
        if c not in prev_end:
            continue                                                   # bu sahnede ilk kez görünen oyuncu: başlangıcı serbest
        p = float(prev_end[c]); x0 = float(m["x0"]); gap = abs(x0 - p)
        if gap <= 1e-9:
            continue
        moving = m["kind"] in MOVING
        hk = max(0.5, heights.get(c, 1.7) / 1.7)
        note = {"rule": "continuity_approach", "kind": "bridged", "actor": c, "from": round(p, 3)}
        if moving:
            m["x0"] = p
            dist = abs(float(m["x1"]) - p); ws = float(m.get("walk_s") or dur)
            vmax = VMAX[m["kind"]] * hk
            note.update(to=round(float(m["x1"]), 3), why=f"yürüyüş başlangıcı {x0:.2f} yerine önceki bitiş {p:.2f}; hedef korunur")
            notes.append(note)
            if dist / vmax + ACC_S > 0.85 * ws + 1e-6:
                notes.append({"rule": "continuity_approach", "kind": "conflict", "actor": c,
                              "why": f"{dist:.2f} m yol {ws:.2f} sn'de yürünemez (üst hız {vmax:.1f} m/sn); plan uzamalı ya da önceki planda yerleşmeli"})
            continue
        if gap <= SNAP_M:
            if abs(float(m["x1"]) - x0) <= 1e-9:
                m["x1"] = p
            m["x0"] = p
            continue
        vmax = VMAX["walk"] * hk
        ws = round(max(0.9, (gap / vmax + ACC_S) / 0.85), 3)
        m["approach"] = {"from": p, "walk_s": ws}
        note.update(to=round(x0, 3), why=f"önceki bitiş {p:.2f} → işaret {x0:.2f}: {gap:.2f} m yürünür ({ws:.2f} sn), sonra '{m['kind']}'")
        notes.append(note)
        if ws > dur:
            notes.append({"rule": "continuity_approach", "kind": "conflict", "actor": c, "why": f"işarete yürüyüş {ws:.2f} sn, plan {dur:.2f} sn: oyuncu planda yetişemiyor"})
        deadline, why = contact_deadline(objects, c)
        if deadline is not None and 0.85 * ws > deadline + 1e-6:
            notes.append({"rule": "continuity_approach", "kind": "conflict", "actor": c,
                          "why": f"{why} teması {deadline:.2f}. sn'de, işarete varış {0.85 * ws:.2f}. sn: temas geç başlamalı ya da önceki planda yerleşmeli"})
        rc = (react or {}).get(c)
        if rc and float(rc["t"]) < ws - 1e-6:
            notes.append({"rule": "continuity_approach", "kind": "conflict", "actor": c,
                          "why": f"tepki {float(rc['t']):.2f}. sn'de başlıyor, işarete yürüyüş {ws:.2f}. sn'de bitiyor"})
    return notes + _crossings(motion, prev_end, shared, {n["actor"] for n in notes})


def _crossings(motion, prev_end, shared, bridged):
    """Sürekliliği sağlayan yürüyüş iki oyuncunun sağ-sol sırasını değiştiriyorsa birbirinin içinden geçer: okunabilirlik sorunu AÇIKÇA bildirilir
    (motor işaretleri değiştirmez; yönetmen planı/bloklamayı düzeltmeli ya da derinlik/kamera çözümü gerekir)."""
    out = []
    end = lambda c: float(motion[c]["x1"] if motion[c]["kind"] in MOVING else motion[c]["x0"])
    for i, a in enumerate(shared):
        for b in shared[i + 1:]:
            if (a in bridged or b in bridged) and (float(prev_end[a]) - float(prev_end[b])) * (end(a) - end(b)) < 0:
                who = a if a in bridged else b
                out.append({"rule": "continuity_crossing", "kind": "conflict", "actor": who,
                            "why": f"{a} ve {b} işaretlerine giderken sağ-sol sırası değişiyor: birbirinin içinden geçip örtüyorlar"})
    return out


def transition_kind(prev, cur):
    """prev/cur: {'scene_id','loc','transition'}; cur.transition açıksa o geçerlidir."""
    t = (cur.get("transition") or "").strip().lower()
    if t in ("time_skip", "cut", "continuous", "scene_change"):
        return t
    if prev is None:
        return "scene_change"
    if prev.get("scene_id") != cur.get("scene_id") or (prev.get("loc") or None) != (cur.get("loc") or None):
        return "scene_change"
    return "continuous"


def carry_starts(motion, prev_end, kind, seed_of=None):
    """Planlayıcının varsayılan başlangıçlarını önceki bitişe bağlar (yalnız sürekli geçişte). Çakışmaları ayırır.
    motion yerinde değişir; dönüş: değişen aktörler."""
    if kind in FREE or not prev_end:
        return []
    changed = []
    for c, m in motion.items():
        if c in prev_end and abs(m["x0"] - prev_end[c]) > 1e-6:
            moved = m["x1"] != m["x0"]
            m["x0"] = max(-XLIM, min(XLIM, float(prev_end[c])))
            m["x1"] = sm.move_target(m["kind"], m["x0"], m.get("seed", 0)) if moved else m["x0"]
            changed.append(c)
    order = sorted(motion, key=lambda c: motion[c]["x0"])
    pos = [motion[c]["x0"] for c in order]
    for k in range(1, len(pos)):                              # soldan sağa: en az MIN_SEP aralık
        pos[k] = max(pos[k], pos[k - 1] + MIN_SEP)
    over = pos[-1] - XLIM
    if over > 0:                                              # sağdan taşarsa hepsini sola kaydır (sahne sınırı)
        pos = [x - over for x in pos]
        pos[0] = max(pos[0], -XLIM)
        for k in range(1, len(pos)):
            pos[k] = max(pos[k], pos[k - 1] + MIN_SEP)
    for c, nx in zip(order, pos):
        m = motion[c]
        if abs(nx - m["x0"]) > 1e-9:
            was = m["x1"] != m["x0"]
            m["x0"] = nx
            m["x1"] = sm.move_target(m["kind"], nx, m.get("seed", 0)) if was else nx
            if c not in changed:
                changed.append(c)
    return changed


def _empty_world():
    return {"actors": {}, "objects": {}}


def _absorb(world, shot):
    world["actors"].update({c: dict(v) for c, v in (shot["exit"]["actors"] or {}).items()})
    world["objects"].update({o: dict(v) for o, v in (shot["exit"]["objects"] or {}).items() if v is not None})


def _moved(a, b, tol):
    pa, pb = a.get("pos"), b.get("pos")
    if pa is not None and pb is not None:
        return max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1])) > tol
    return a.get("at") != b.get("at")                                  # koordinat çözülemiyorsa ad/ham değer karşılaştırılır


def check(shots, tol=TOL_M):
    """shots: sözleşme planları (entry/exit durumlu). Dönüş: sorun listesi (sorumlu motor adıyla).
    Karşılaştırma yalnız bir önceki planla değil, birikmiş dünya durumuyladır."""
    out = []; prev = None; world = _empty_world()
    for s in shots:
        k = transition_kind(prev, s)
        s["transition_kind"] = k
        if k in FREE:
            world = _empty_world()
        else:
            for c, st in (s["entry"]["actors"] or {}).items():
                pe = world["actors"].get(c)
                if pe is not None and st.get("x") is not None and pe.get("x") is not None and abs(st["x"] - pe["x"]) > tol:
                    out.append({"rule": "TELEPORT", "shot": s["shot_id"], "actor": c, "from": pe["x"], "to": st["x"], "gap_m": round(abs(st["x"] - pe["x"]), 3),
                                "transition": k, "engine": "staging", "why": f"{k} geçişinde {c} {pe['x']:.2f} -> {st['x']:.2f} m sıçradı; açık time_skip/scene_change yok"})
            entry_o = s["entry"]["objects"] or {}
            cast = s.get("cast") or list(s["entry"]["actors"] or {})
            for o, po in world["objects"].items():
                st = entry_o.get(o)
                base = {"shot": s["shot_id"], "object": o, "transition": k, "engine": "object_state"}
                if st is None:
                    if not po.get("hidden") and (po.get("holder") is None or po["holder"] in cast):
                        out.append(dict(base, rule="OBJECT_VANISH", why=f"{o} önceki durumda {'elde: ' + po['holder'] if po.get('holder') else 'sahnede'}; bu planda izi yok (kayboluyor)"))
                elif po.get("hidden"):
                    if not st.get("hidden"):
                        out.append(dict(base, rule="OBJECT_JUMP", why=f"{o} imha edilmişti; olay olmadan yeniden ortaya çıktı"))
                elif st.get("holder") != po.get("holder"):
                    out.append(dict(base, rule="OBJECT_JUMP", **{"from": po.get("holder"), "to": st.get("holder")},
                                    why=f"{o} sahibi plan sınırında {po.get('holder')} -> {st.get('holder')} oldu; olay yok"))
                elif st.get("holder") is None and _moved(po, st, tol):
                    out.append(dict(base, rule="OBJECT_JUMP", **{"from": po.get("at"), "to": st.get("at")},
                                    why=f"{o} elde olmadan yer değiştirdi: {po.get('at')} -> {st.get('at')}; olay yok"))
        _absorb(world, s)
        prev = s
    return out


def resume_state(shots, shot_id):
    """Yeniden başlatma: verilen planın başlangıcında geçerli olması gereken BİRİKMİŞ dünya durumu.
    İlk plan ya da serbest geçişle başlayan plan için None (taşınacak durum yok)."""
    prev = None; world = _empty_world()
    for s in shots:
        k = transition_kind(prev, s)
        if k in FREE:
            world = _empty_world()
        if s["shot_id"] == shot_id:
            return None if k in FREE else copy.deepcopy(world)
        _absorb(world, s); prev = s
    raise KeyError(shot_id)
