"""AHOS aksiyon bloklaması ve kamerası (genel motor; proje adı/koordinatı bilmez). Okunabilirlik ölçütü ayrı modüldedir: readability.py.

1) BLOKLAMA (resolve): YALNIZ temas olayı olan planlarda; temasa KATILMAYAN, duran eylemdeki oyuncu (seyirci) başkasının içinden geçmek zorunda kalıyorsa ya da atış/bırakma
   koridorunda (atan ile hedef arasında) duruyorsa, işaretine en yakın uygun konuma alınır. Temasa katılanlar, yürüyen oyuncular ve hikâye DEĞİŞTİRİLMEZ.
   Yönetmenin işareti değiştiyse 'intent_x' ile açıkça raporlanır; uygun konum yoksa 'conflict' (sessizce geçilmez -> sözleşme kapısı).
2) DERİNLİK (draw_order): aksiyonlu planda temasa katılanlar seyircinin önünde, katılanlardan KISA olan uzun olanın önünde çizilir. Plan boyunca sabittir.
3) KAMERA (framing): temas penceresinde tek ve sabit bir 'aksiyon' kadrajı: katılanlar, eller, nesnenin yerleri ve hedef birlikte; tepki/yakın plan kesmesi yapılmaz."""
import continuity
import object_state
import setpieces2d
import props2d
import shot_motion as sm

BODY_K = 0.30             # karakterin yarı genişliği / boy (çizgi film başı dahil); iki oyuncunun örtüşmeden durma aralığı = BODY_K*(Ha+Hb)
CORRIDOR_PAD = 0.20       # atış koridorunun iki ucuna eklenen pay (hedef ağzının yarı genişliği, m); seyircinin yarı genişliği ayrıca eklenir
PATH_SEP = 0.20           # yürürken izin verilen en az merkez aralığı (m); altı 'içinden geçme'
HOLD_LEAD, HOLD_TAIL = 0.6, 0.6      # aksiyon kadrajı olaydan bu kadar önce kurulur / sonra bırakılır (sn)
GROUND_PX, TOP_PX, SIDE_PX = 590.0, 40.0, 80.0     # 1280x720: zemin ön plan çiminin üstünde kalsın; baş ve kenar payı
ZOOM_MIN, ZOOM_MAX, ZOOM_ALL_MIN = 0.8, 1.7, 0.9


def participants(objects):
    """Temas olayı olan ya da elinde nesne olan oyuncular."""
    out = set()
    for ob in objects or []:
        tr = ob.get("track") or []
        out.update(k["holder"] for k in tr if k.get("holder"))
        for e in object_state.events(tr):
            out.update(c for c in (e["by"], e.get("to")) if c)
    return out


def _end(m):
    return float(m["x1"] if m["kind"] in continuity.MOVING else m["x0"])


def corridors(motion, objects, targets):
    """Atış/bırakma koridorları: [(lo, hi, atan, hedef)]."""
    out = []
    for ob in objects or []:
        tr = ob.get("track") or []
        for e in object_state.events(tr):
            if e["type"] not in ("dispose", "drop") or e["by"] not in motion:
                continue
            for k in tr:
                if k.get("t") == e["t"] and isinstance(k.get("at"), str) and k["at"] in (targets or {}):
                    hx, tx = _end(motion[e["by"]]), float(targets[k["at"]][0])
                    out.append((min(hx, tx) - CORRIDOR_PAD, max(hx, tx) + CORRIDOR_PAD, e["by"], k["at"]))
    return out


def _path_ok(cid, cand, motion, prev_x, heights, dur):
    """Aday hareket boyunca hiçbir oyuncunun içinden geçmiyor mu? (sağ-sol sırası korunur, aralık çizilen konumlarla ölçülür)"""
    n = max(8, int(dur * 12))
    for other, om in motion.items():
        if other == cid:
            continue
        side = None
        if cid in prev_x and other in prev_x:
            side = 1.0 if prev_x[cid] >= prev_x[other] else -1.0
        for i in range(n + 1):
            t = dur * i / n
            d = sm.motion_x(cand, t, dur, heights.get(cid, 1.2)) - sm.motion_x(om, t, dur, heights.get(other, 1.2))
            if side is None:
                side = 1.0 if d >= 0 else -1.0
            if d * side < PATH_SEP - 1e-9:
                return False
    return True


def _candidate(m, p, x, heights, cid):
    c = {k: v for k, v in m.items() if k != "approach"}
    c["x0"] = c["x1"] = x
    if p is not None:
        gap = abs(x - p)
        if gap <= continuity.SNAP_M:
            c["x0"] = c["x1"] = p
        else:
            vmax = continuity.VMAX["walk"] * max(0.5, heights.get(cid, 1.7) / 1.7)
            c["approach"] = {"from": p, "walk_s": round(max(0.9, (gap / vmax + continuity.ACC_S) / 0.85), 3)}
    return c


def resolve(motion, objects, heights, targets, prev_x, kind, dur, react=None):
    """motion yerinde değişir (yalnız seyirciler). Dönüş: notlar [{'rule':'blocking'|'continuity_crossing',...}] — reconcile notlarıyla birleştirmek için merge() kullanın."""
    notes = []
    prev_x = {} if kind in continuity.FREE else {c: float(v) for c, v in (prev_x or {}).items() if c in motion}
    if not any(object_state.events(ob.get("track") or []) for ob in objects or []):
        return []                                                  # temas olayı yok: bloklama yönetmenindir; geçişme yalnız raporlanır (continuity)
    act = participants(objects)
    cor = corridors(motion, objects, targets)
    shared = sorted(prev_x)
    bridged = {c for c, m in motion.items() if m.get("approach") or (c in prev_x and m["kind"] in continuity.MOVING)}
    crossing = set()
    for n in continuity._crossings(motion, prev_x, shared, bridged):
        pair = n["why"].split(" işaretlerine")[0].split(" ve ")
        crossing.update(pair)
    for cid in sorted(motion):
        m = motion[cid]
        if cid in act or m["kind"] in continuity.MOVING:
            continue
        mark = float(m["x0"])
        half = BODY_K * heights.get(cid, 1.2)                      # gövde genişliği: merkez dışarıda olsa da gövde hedefi örtebilir
        in_cor = next((c for c in cor if c[0] - half < mark < c[1] + half), None)
        if cid not in crossing and in_cor is None:
            continue
        reason = f"atış koridorunda ({in_cor[2]} → {in_cor[3]})" if in_cor else "işaretine giderken başka oyuncunun içinden geçiyor"
        p = prev_x.get(cid)
        rc = (react or {}).get(cid)
        best = None
        grid = [round(-continuity.XLIM + 0.05 * i, 2) for i in range(int(round(2 * continuity.XLIM / 0.05)) + 1)]
        for x in sorted(grid, key=lambda v: (abs(v - mark), v)):
            if any(lo - half < x < hi + half for lo, hi, *_ in cor):
                continue
            if any(abs(x - _end(om)) < max(continuity.MIN_SEP, BODY_K * (heights.get(cid, 1.2) + heights.get(o, 1.2))) - 1e-9
                   for o, om in motion.items() if o != cid):
                continue
            cand = _candidate(m, p, x, heights, cid)
            ap = cand.get("approach")
            if ap and (ap["walk_s"] > dur or (rc and float(rc["t"]) < ap["walk_s"] - 1e-6)):
                continue
            if not _path_ok(cid, cand, motion, prev_x, heights, dur):
                continue
            best = (x, cand); break
        if best is None:
            notes.append({"rule": "blocking", "kind": "conflict", "actor": cid,
                          "why": f"{cid} {reason}; sağ-sol sırasını, aralığı ve koridoru birlikte sağlayan konum yok: plan bölünmeli ya da bloklama yeniden yazılmalı"})
            continue
        motion[cid] = best[1]
        notes.append({"rule": "blocking", "kind": "adjusted", "actor": cid, "intent_x": round(mark, 3), "to": round(best[0], 3),
                      "why": f"seyirci {cid} {reason}: işaret {mark:.2f} → {best[0]:.2f} m (eylem '{m['kind']}' korunur)"})
    return notes


def merge(stage_notes, block_notes, motion, prev_x, kind):
    """Bloklama bir oyuncuyu yeniden yerleştirdiyse onun eski süreklilik notları geçersizdir; geçişme denetimi son hareketle YENİDEN yapılır."""
    moved = {n["actor"] for n in block_notes if n["kind"] == "adjusted"}
    if not moved:
        return stage_notes + block_notes
    out = [n for n in stage_notes if not (n.get("rule") == "continuity_crossing" or (n.get("rule") == "continuity_approach" and n.get("actor") in moved))]
    prev = {} if kind in continuity.FREE else {c: float(v) for c, v in (prev_x or {}).items() if c in motion}
    bridged = {c for c, m in motion.items() if m.get("approach") or (c in prev and m["kind"] in continuity.MOVING)}
    return out + block_notes + continuity._crossings(motion, prev, sorted(prev), bridged)


def _events(beat):
    return [e for ob in (beat.get("choreo") or {}).get("objects", []) for e in object_state.events(ob.get("track") or [])]


def draw_order(beat, designs, items):
    """items: [(cid, tasarım, poz, ...)] -> arkadan öne sıra."""
    act = {c for e in _events(beat) for c in (e["by"], e.get("to")) if c}
    if not act:
        return sorted(items, key=lambda it: it[2]["x"])
    return sorted(items, key=lambda it: (it[0] in act, -it[1]["height"] if it[0] in act else 0.0, it[2]["x"]))


def hold_windows(beat):
    """Birleştirilmiş aksiyon kadrajı pencereleri: [(t0, t1, olaylar)] (vuruş içi sn)."""
    dur = beat["t_end"] - beat["t_start"]
    spans = sorted(((max(0.0, e["t_start"] - HOLD_LEAD), min(dur, e["t"] + HOLD_TAIL), e) for e in _events(beat)), key=lambda s: s[:2])
    out = []
    for a, b, e in spans:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b), out[-1][2] + [e])
        else:
            out.append((a, b, [e]))
    return out


def _fit(xs_lo, xs_hi, top_m, base_ppm):
    zw = (1280.0 - 2 * SIDE_PX) / max(0.1, xs_hi - xs_lo) / base_ppm
    zh = (GROUND_PX - TOP_PX) / max(0.1, top_m) / base_ppm
    return min(zw, zh)


def framing(beat, designs, lt, base_ppm):
    """Aksiyon penceresindeysek sabit kadraj {'cx','cy','zoom','whole_cast'}; değilse None. Pencere boyunca aynı değerdir (titreme/kesme yok)."""
    win = next((w for w in hold_windows(beat) if w[0] <= lt <= w[1]), None)
    if win is None:
        return None
    a, b, evs = win
    dur = beat["t_end"] - beat["t_start"]
    mo = beat["motion"]

    def box(actors):
        lo, hi, top = [], [], [1.0]
        for c in actors:
            H = designs[c]["height"]
            for i in range(13):
                x = sm.motion_x(mo[c], a + (b - a) * i / 12, dur, H)
                lo.append(x - BODY_K * H); hi.append(x + BODY_K * H)
            top.append(H * 1.08)
        for ob in (beat.get("choreo") or {}).get("objects", []):
            tr = ob.get("track") or []
            if not any(e in object_state.events(tr) for e in evs):
                continue
            for k in tr:
                at = k.get("at")
                at = (beat.get("targets") or {}).get(at) if isinstance(at, str) else at
                if at is not None:
                    lo.append(at[0] - 0.30); hi.append(at[0] + 0.30); top.append(at[1] + 0.35)
            for k0, k1 in zip(tr, tr[1:]):                              # kap içine atışın yay tepesi de kadrajda kalır
                g = setpieces2d.mouth_of(k1.get("at")) if "holder" in k0 and k1.get("hide") else None
                if g and k0["holder"] in mo and k1["at"] in (beat.get("targets") or {}):
                    H = designs[k0["holder"]]["height"]
                    dx = abs(beat["targets"][k1["at"]][0] - sm.motion_x(mo[k0["holder"]], k0["t"], dur, H))
                    top.append(max(0.8 * H, g["rim"]) + max(object_state.SINK_CLEAR_MIN, object_state.SINK_CLEAR_K * dx)
                               + sum(props2d.extent(ob.get("prop", ""), ob.get("scale", 0.55))[:2]))
        return (min(lo), max(hi), max(top)) if lo else None
    act = [c for c in sorted({c for e in evs for c in (e["by"], e.get("to")) if c}) if c in mo and c in designs]
    if not act:
        return None
    whole = box([c for c in beat["cast"] if c in mo and c in designs])
    use, whole_cast = whole, True
    if _fit(whole[0], whole[1], whole[2], base_ppm) < ZOOM_ALL_MIN:            # herkes sığmıyorsa yalnız aksiyon kadrajlanır
        use, whole_cast = box(act), False
    zoom = max(ZOOM_MIN, min(ZOOM_MAX, _fit(use[0], use[1], use[2], base_ppm)))
    s = base_ppm * zoom
    return {"cx": (use[0] + use[1]) / 2, "cy": (GROUND_PX - 360.0) / s, "zoom": zoom, "whole_cast": whole_cast}
