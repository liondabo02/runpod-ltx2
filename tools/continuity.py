"""AHOS planlar arası süreklilik (genel motor kuralı; proje verisi bilmez).
Geçiş türleri (bir planın BAŞINDAKİ sınır):
  continuous / cut : dünya durumu sürer (kamera kesmesi aktörü ışınlamaz)
  time_skip        : açık anlatısal zaman atlaması (konum değişimine izin verir)
  scene_change     : sahne/mekân değişti (çıkarım; izin verir)
Işınlanma = bu iki serbest türün dışında konum/nesne sahibi sıçraması -> reddedilir (TELEPORT / OBJECT_JUMP)."""
import shot_motion as sm

FREE = ("time_skip", "scene_change")
TOL_M = 0.15            # aynı dünya durumu sayılan konum farkı (metre)
MIN_SEP = 0.6           # iki aktörün en az aralığı (metre)
XLIM = 1.9


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


def check(shots, tol=TOL_M):
    """shots: sözleşme planları (entry/exit durumlu). Dönüş: sorun listesi (sorumlu motor adıyla)."""
    out = []; prev = None
    for s in shots:
        k = transition_kind(prev, s)
        s["transition_kind"] = k
        if prev is not None and k not in FREE:
            for c, st in (s["entry"]["actors"] or {}).items():
                pe = (prev["exit"]["actors"] or {}).get(c)
                if pe is not None and st.get("x") is not None and pe.get("x") is not None and abs(st["x"] - pe["x"]) > tol:
                    out.append({"rule": "TELEPORT", "shot": s["shot_id"], "actor": c, "from": pe["x"], "to": st["x"], "gap_m": round(abs(st["x"] - pe["x"]), 3),
                                "transition": k, "engine": "staging", "why": f"{k} geçişinde {c} {pe['x']:.2f} -> {st['x']:.2f} m sıçradı; açık time_skip/scene_change yok"})
            for o, st in (s["entry"]["objects"] or {}).items():
                po = (prev["exit"]["objects"] or {}).get(o)
                if po is not None and (st.get("holder") != po.get("holder")):
                    out.append({"rule": "OBJECT_JUMP", "shot": s["shot_id"], "object": o, "from": po.get("holder"), "to": st.get("holder"),
                                "transition": k, "engine": "object_state", "why": f"{o} sahibi plan sınırında {po.get('holder')} -> {st.get('holder')} oldu; olay yok"})
        prev = s
    return out


def resume_state(shots, shot_id):
    """Yeniden başlatma: verilen planın başlangıcında geçerli olması gereken durum (önceki planın bitişi)."""
    prev = None
    for s in shots:
        if s["shot_id"] == shot_id:
            return None if prev is None else {"actors": dict(prev["exit"]["actors"]), "objects": dict(prev["exit"]["objects"])}
        prev = s
    raise KeyError(shot_id)
