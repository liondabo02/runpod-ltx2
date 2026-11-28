"""AHOS aksiyon bloklaması ve kamerası (genel motor; proje adı/koordinatı bilmez). Okunabilirlik ölçütü ayrı modüldedir: readability.py.

1) BLOKLAMA (resolve): YALNIZ temas olayı olan planlarda; temasa KATILMAYAN, duran eylemdeki oyuncu (seyirci) başkasının içinden geçmek zorunda kalıyorsa ya da atış/bırakma
   koridorunda (atan ile hedef arasında) duruyorsa, işaretine en yakın uygun konuma alınır. Temasa katılanlar, yürüyen oyuncular ve hikâye DEĞİŞTİRİLMEZ.
   Yönetmenin işareti değiştiyse 'intent_x' ile açıkça raporlanır; uygun konum yoksa 'conflict' (sessizce geçilmez -> sözleşme kapısı).
2) DERİNLİK (draw_order): aksiyonlu planda temasa katılanlar seyircinin önünde, katılanlardan KISA olan uzun olanın önünde çizilir. Plan boyunca sabittir.
4) TEMASSIZ ÖRTME (separate): temas olayı olmayan planda eşit/yakın boylu iki oyuncu uzun süre üst üste kalırsa işaretlerden biri en az kaydırmayla ayrılır.
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
# temassız örtme bloklaması: eşit/yakın boylu iki oyuncu yüz örtmemek için merkezleri en az OCCL_SEP_K * ortalama boy ayrı durur (piksel ölçüsüyle sınandı)
OCCL_SEP_K, OCCL_MAX_S, OCCL_FPS = 0.58, 1.0, 4
OCCL_SHIFT_MAX = 1.2      # bir işaret en çok bu kadar kaydırılır (m)


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


def needs_head_sep(a, b):
    """İki tasarım üst üste geldiğinde çizim sırası yüzü kurtaramıyor mu? Kısa olan önde çizilir; tepesi uzunun çenesinin üstüne çıkıyorsa
    (eşit/yakın boy) öndeki arkadakinin yüzünü kapatır: o zaman yan yana aralık gerekir."""
    import puppet2d as pp                                   # yalnız tasarım oranı için; planlayıcı çizim modülü olmadan da yüklenebilir
    short, tall = sorted((a, b), key=lambda d: d["height"])
    return short["height"] > tall["height"] * (1.0 - pp.head_share(tall))


def head_sep_m(a, b):
    return OCCL_SEP_K * (a["height"] + b["height"]) / 2


def _long_overlap(ma, mb, a, b, dur):
    """İki hareket, gerekli aralıktan OCCL_MAX_S'den uzun süre daha yakın mı? Dönüş: en uzun kesintisiz süre (sn) ya da 0."""
    need = head_sep_m(a, b); step = 1.0 / OCCL_FPS; run = worst = 0
    for k in range(int(dur * OCCL_FPS)):
        t = (k + 0.5) * step
        close = abs(sm.motion_x(ma, t, dur, a["height"]) - sm.motion_x(mb, t, dur, b["height"])) < need - 1e-9
        run = run + 1 if close else 0
        worst = max(worst, run)
    return worst * step if worst * step > OCCL_MAX_S + 1e-9 else 0.0


def _blocked_pairs(motion, designs, dur):
    ids = sorted(c for c in motion if c in designs)
    return [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]
            if needs_head_sep(designs[a], designs[b]) and _long_overlap(motion[a], motion[b], designs[a], designs[b], dur)]


def _shifted(m, dx, which, p, heights, cid, free):
    """İşareti dx kaydırılmış hareket. which: 'mark' (duran: tek işaret) | 'end' (yürüyüşün hedefi) | 'start' (yalnız serbest geçişte başlangıç)."""
    if which == "mark":
        x = round(float(m["x0"]) + dx, 3)
        if abs(x) > continuity.XLIM:
            return None
        return _candidate(m, None if free else p, x, heights, cid)
    key = "x1" if which == "end" else "x0"
    x = round(float(m[key]) + dx, 3)
    d0 = float(m["x1"]) - float(m["x0"])
    c = dict(m, **{key: x})
    if abs(x) > continuity.XLIM or (float(c["x1"]) - float(c["x0"])) * d0 <= 0:      # yürüyüş yönü tersine dönmez
        return None
    return c


def separate(motion, objects, designs, prev_x, kind, dur, react=None, locked=()):
    """TEMASSIZ planda yüz örtmesini bloklama KENDİSİ çözer: çizim sırasının kurtaramadığı (eşit/yakın boy) iki oyuncu OCCL_MAX_S'den uzun
    süre üst üste kalıyorsa birinin işareti en az kaydırmayla ayrılır. Duran seyirci yürüyenden, nesnesiz oyuncu nesne tutandan önce oynatılır;
    sağ-sol sırası, süreklilik (önceki bitişten yürüyerek) ve yürüyüş yönü korunur. Temas olaylı planlara dokunmaz. motion yerinde değişir.
    Çözülemeyen çift 'unresolved' notu alır; son sözü piksel ölçüsüne dayanan render kapısı söyler."""
    if any(object_state.events(ob.get("track") or []) for ob in objects or []):
        return []
    free = kind in continuity.FREE or not prev_x
    prev_x = {} if free else {c: float(v) for c, v in prev_x.items() if c in motion}
    heights = {c: designs[c]["height"] for c in motion if c in designs}
    holders = participants(objects)
    notes = []
    for _round in range(len(motion)):
        pairs = _blocked_pairs(motion, designs, dur)
        if not pairs:
            return notes
        a, b = pairs[0]
        options = []
        for cid in (a, b):
            if cid in locked:                               # süreklilik çelişkisi olan oyuncu oynatılmaz: çelişki notu silinmeden kapıya gider
                continue
            m = motion[cid]
            if m["kind"] in continuity.MOVING:
                whichs = ["end"] + ([] if cid in prev_x else ["start"])
            else:
                whichs = ["mark"]
            for which in whichs:
                options.append((m["kind"] in continuity.MOVING, cid in holders, cid, which))
        best = None
        for step in range(1, int(round(OCCL_SHIFT_MAX / 0.05)) + 1):        # önce en küçük kaydırma; eşitlikte duran ve eli boş oyuncu
            for moving, holds, cid, which in sorted(options):
                for dx in (0.05 * step, -0.05 * step):
                    cand = _shifted(motion[cid], dx, which, prev_x.get(cid), heights, cid, cid not in prev_x)
                    if cand is None:
                        continue
                    if which == "end":                      # uzayan yol plan süresinde yürünebilir kalmalı
                        vmax = continuity.VMAX[cand["kind"]] * max(0.5, heights[cid] / 1.7)
                        if abs(float(cand["x1"]) - float(cand["x0"])) / vmax + continuity.ACC_S > 0.85 * float(cand.get("walk_s") or dur) + 1e-6:
                            continue
                    ap = cand.get("approach")
                    rc = (react or {}).get(cid)
                    if ap and (ap["walk_s"] > dur or (rc and float(rc["t"]) < ap["walk_s"] - 1e-6)):
                        continue
                    trial = dict(motion, **{cid: cand})
                    if any((sm.motion_x(motion[cid], t, dur, heights[cid]) - sm.motion_x(motion[o], t, dur, heights[o]))
                           * (sm.motion_x(cand, t, dur, heights[cid]) - sm.motion_x(motion[o], t, dur, heights[o])) < 0
                           for o in heights if o != cid for t in (0.0, dur)):      # sağ-sol sırası plan başında ve sonunda aynı kalır
                        continue
                    left = _blocked_pairs(trial, designs, dur)
                    if len(left) < len(pairs) and not set(left) - set(pairs):
                        best = (cid, which, cand); break
                if best:
                    break
            if best:
                break
        if best is None:
            break
        cid, which, cand = best
        key = "x1" if which == "end" else "x0"
        old = float(motion[cid][key])
        motion[cid] = cand
        other = b if cid == a else a
        notes.append({"rule": "blocking", "kind": "adjusted", "actor": cid, "intent_x": round(old, 3), "to": round(float(cand[key]), 3),
                      "why": f"{cid} ile {other} {OCCL_MAX_S:.1f} sn'den uzun üst üste kalıp yüz örtüyordu: {cid} {'yürüyüş hedefi' if which == 'end' else 'işareti'} {old:.2f} → {float(cand[key]):.2f} m"})
    for a, b in _blocked_pairs(motion, designs, dur):
        notes.append({"rule": "blocking", "kind": "unresolved", "actor": a, "why": f"{a} ve {b} yüz örtmeyecek aralığa ayrılamadı: plan bölünmeli ya da bloklama yeniden yazılmalı"})
    return notes


def _events(beat):
    return [e for ob in (beat.get("choreo") or {}).get("objects", []) for e in object_state.events(ob.get("track") or [])]


def draw_order(beat, designs, items):
    """items: [(cid, tasarım, poz, ...)] -> arkadan öne sıra. Temasa katılanlar katılmayanların önünde; her grupta uzun arkada, kısa önde:
    kısa oyuncu uzunun yalnız gövdesini örter, uzunun yüzü üstte açık kalır. Sıra x'e bağlı değildir (yan yana geçerken katman yer değiştirmez);
    eşit boyda x belirler."""
    act = {c for e in _events(beat) for c in (e["by"], e.get("to")) if c}
    return sorted(items, key=lambda it: (it[0] in act, -it[1]["height"], it[2]["x"]))


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
