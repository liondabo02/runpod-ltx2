"""AHOS gösterme jesti (diziden bağımsız): hedefi OLAN bir jesttir ve hedef veride taşınır.

Vuruş verisi: choreo["points"] = [{"by": oyuncu, "to": hedef, "line": n, "t": sn, "dur": sn}]
  hedef: {"prop": nesne}   o andaki nesne (yerde ya da birinin elinde)
         "oyuncu_kimliği"  diğer oyuncu
         "hedef_adi"       planın mekân hedefi (plan['targets'])
         [x, y]            dünya noktası (proje verisi)
  zaman: 'line' verilirse jest, gösterenin bu vuruştaki n. replikiyle başlar ve onunla biter; o replik yoksa 't' + 'dur' (vuruş içi sn).
Aynı veriyi üç motor okur: poz (kol hedefe uzanır), kamera (jest boyunca gösteren ve hedef aynı sabit kadrajda), okunabilirlik ölçüsü."""
import action_staging
import continuity
import object_state
import props2d
import puppet2d as pp
import scenes2d as sc
import shot_motion as sm

RAMP_S = 0.3            # kol bu sürede kalkar / iner
MIN_HOLD_S = 1.4        # jest ve kadrajı bundan kısa olmaz (göz kolu izleyip hedefe gidecek zaman bulsun)
TAIL_S = 0.3            # kol inerken kadraj hedefte kalır
BODY_LOW_K = 0.18       # bloklama denetiminde baş altı gövdenin yarı genişliği / boy
LOOK_TOP_M = 0.35       # kadrajda hedefin üstünde kalan pay
SIDE_M = 0.30           # hedefin iki yanındaki pay


def items(beat):
    return list((beat.get("choreo") or {}).get("points") or [])


def span(beat, item):
    """Jestin (başlangıç, bitiş) aralığı, vuruş içi sn; zaman verisi yoksa None."""
    dur = beat["t_end"] - beat["t_start"]
    a = b = None
    n = item.get("line")
    if n is not None:
        mine = sorted((ln for ln in beat.get("lines") or [] if ln["char"] == item.get("by")), key=lambda ln: ln["start"])
        if 0 <= int(n) < len(mine):
            a, b = mine[int(n)]["start"] - beat["t_start"], mine[int(n)]["end"] - beat["t_start"]
    if a is None:
        if item.get("t") is None:
            return None
        a = float(item["t"]); b = a + float(item.get("dur", MIN_HOLD_S))
    b = max(b, a + MIN_HOLD_S)
    if b > dur:
        a, b = max(0.0, a - (b - dur)), dur
    return max(0.0, a), b


def problem(beat, item):
    """Veri olarak çözülemeyen jest için gerekçe; çözülüyorsa None."""
    cast = beat.get("cast") or []
    if item.get("by") not in cast or item.get("by") not in (beat.get("motion") or {}):
        return f"gösteren '{item.get('by')}' bu vuruşun kadrosunda değil"
    if span(beat, item) is None:
        return "jestin zamanı yok: 't' verilmemiş ve gösterenin istenen repliki bulunamadı"
    to = item.get("to")
    if isinstance(to, dict):
        if not any(ob.get("prop") == to.get("prop") and ob.get("track") for ob in (beat.get("choreo") or {}).get("objects", [])):
            return f"gösterilen nesne '{to.get('prop')}' vuruşun nesne izlerinde yok"
    elif isinstance(to, str):
        if to == item.get("by") or (to not in cast and to not in (beat.get("targets") or {})):
            return f"gösterilen hedef '{to}' ne diğer bir oyuncu ne de planın bir mekân hedefi"
    elif not (isinstance(to, (list, tuple)) and len(to) == 2):
        return "jestin hedefi yok"
    return None


def windows(beat):
    """Çözülen jestler: [(a, b, item)] zaman sırasıyla (vuruş içi sn)."""
    out = [span(beat, it) + (it,) for it in items(beat) if problem(beat, it) is None]
    return sorted(out, key=lambda w: w[:2])


def shot_windows(beat):
    """Kameranın gösterme kadrajında kaldığı aralıklar: [(a, b, [jestler])]; arası MIN_HOLD_S'den kısa jestler tek çekimdir."""
    dur = beat["t_end"] - beat["t_start"]
    out = []
    for a, b, it in windows(beat):
        b = min(dur, b + TAIL_S)
        if out and a - out[-1][1] < MIN_HOLD_S:
            out[-1] = (out[-1][0], max(out[-1][1], b), out[-1][2] + [it])
        else:
            out.append((a, b, [it]))
    return out


def window_at(beat, lt):
    return next((w for w in shot_windows(beat) if w[0] <= lt <= w[1]), None)


def target_box(beat, designs, item, lt):
    """Gösterilen şeyin dünya kutusu (x_merkez, y_alt, y_üst, yarı_genişlik), yalnız plan verisinden; yoksa None."""
    to, dur = item.get("to"), beat["t_end"] - beat["t_start"]
    mo = beat.get("motion") or {}

    def actor_x(cid):
        return sm.motion_x(mo[cid], lt, dur, designs[cid]["height"])
    if isinstance(to, dict):
        for ob in (beat.get("choreo") or {}).get("objects", []):
            if ob.get("prop") != to.get("prop") or not ob.get("track"):
                continue

            def place(at):
                at = (beat.get("targets") or {})[at] if isinstance(at, str) else at
                return at[0], at[1]
            x, y, _st = object_state.position(ob["track"], lt, lambda c, _t, _h=None: (actor_x(c), 0.45 * designs[c]["height"]), place)
            if x is None:
                return None
            below, above, half = props2d.extent(ob["prop"], ob.get("scale", 0.55))
            return x, y - below, y + above, half
        return None
    if isinstance(to, str) and to in (beat.get("cast") or []) and to in mo:
        H = designs[to]["height"]
        return actor_x(to), 0.45 * H, H, 0.25 * H
    if isinstance(to, str):
        to = (beat.get("targets") or {}).get(to)
    if to is None:
        return None
    return float(to[0]), float(to[1]) - 0.05, float(to[1]) + 0.05, 0.05


def framing(beat, designs, lt, base_ppm):
    """Gösterme penceresindeysek sabit kadraj {'cx','cy','zoom','whole_cast'}; değilse None.
    Gösteren (bütün boy) ve hedef birlikte kadrajdadır; herkes sığıyorsa bütün kadro. Pencere boyunca tek değerdir."""
    win = window_at(beat, lt)
    if win is None:
        return None
    a, b, its = win
    dur = beat["t_end"] - beat["t_start"]

    def box(actors):
        lo, hi, top = [], [], [1.0]
        times = [a + (b - a) * i / 8 for i in range(9)]
        for c in actors:
            H = designs[c]["height"]
            for t_ in times:
                x = sm.motion_x(beat["motion"][c], t_, dur, H)
                lo.append(x - action_staging.BODY_K * H); hi.append(x + action_staging.BODY_K * H)
            top.append(H * 1.08)
        for it in its:
            for t_ in times:
                tb = target_box(beat, designs, it, t_)
                if tb:
                    lo.append(tb[0] - tb[3] - SIDE_M); hi.append(tb[0] + tb[3] + SIDE_M); top.append(tb[2] + LOOK_TOP_M)
        return min(lo), max(hi), max(top)
    pointers = sorted({it["by"] for it in its if it["by"] in designs})
    if not pointers:
        return None
    use, whole_cast = box([c for c in beat["cast"] if c in beat["motion"] and c in designs]), True
    if action_staging._fit(use[0], use[1], use[2], base_ppm) < action_staging.ZOOM_ALL_MIN:
        use, whole_cast = box(pointers), False
    zoom = max(action_staging.ZOOM_MIN, min(action_staging.ZOOM_MAX, action_staging._fit(use[0], use[1], use[2], base_ppm)))
    return {"cx": (use[0] + use[1]) / 2, "cy": (action_staging.GROUND_PX - 360.0) / (base_ppm * zoom), "zoom": zoom, "whole_cast": whole_cast}


def weight(a, b, lt):
    """Kolun hedefe uzanma ağırlığı 0..1 (yumuşak kalkış ve iniş)."""
    if lt <= a or lt >= b:
        return 0.0
    u = max(0.0, min(1.0, min(lt - a, b - lt) / RAMP_S))
    return u * u * (3 - 2 * u)


def arm_side(des, pose, target_dx):
    """Hedef hangi yandaysa o yandaki kol gösterir (kol gövdenin önünden karşıya uzanamaz)."""
    return "R" if target_dx > 0 else "L"


def hand_hidden(beat, designs, item, motion=None):
    """Bloklama denetimi (poz/piksel gerektirmeyen yaklaşık geometri): jest boyunca gösteren elin ya da ön kolun önünde duran oyuncular.
    Yalnız gösterenden kısa/eşit boylu oyuncu öndedir (çizim sırası). Son söz piksel ölçüsüne dayanan render kapısınındır."""
    motion = motion or beat["motion"]
    a, b = span(beat, item)
    by, dur = item["by"], beat["t_end"] - beat["t_start"]
    des = designs[by]
    out = set()
    for k in range(9):
        t = a + RAMP_S + (max(a + RAMP_S, b - RAMP_S) - a - RAMP_S) * k / 8
        tb = target_box(dict(beat, motion=motion), designs, item, t)
        if tb is None:
            continue
        x = sm.motion_x(motion[by], t, dur, des["height"])
        pose = sm.pose_at("idle", t, dur, motion[by].get("seed", 0), x, x, des["height"], des["height"] * 0.45)
        pose["x"], pose["yaw"], pose["z"], pose["lean"] = x, 0.0, 0.0, 0.0
        side = arm_side(des, pose, tb[0] - x)
        sx, sh = pp.shoulder_offset(des, pose, side)
        vx, vh = tb[0] - x - sx, (tb[1] + tb[2]) / 2 - sh
        dist = max(1e-6, (vx * vx + vh * vh) ** 0.5)
        ln = min(dist, des["height"] * 0.27)
        r = pp.HAND_R_K * des["height"]
        for u in (0.6, 0.8, 1.0):
            hx, hh = x + sx + vx / dist * ln * u, sh + vh / dist * ln * u
            for other, om in motion.items():
                if other == by or other not in designs or other == item.get("to") or designs[other]["height"] > des["height"]:
                    continue
                Ho = designs[other]["height"]
                half = (action_staging.BODY_K if hh >= 0.45 * Ho else BODY_LOW_K) * Ho
                if hh - r < 1.03 * Ho and abs(hx - sm.motion_x(om, t, dur, Ho)) < half + 0.5 * r:
                    out.add(other)
    return sorted(out)


def clear(beat, designs, prev_x, kind, react=None, locked=()):
    """Gösteren elin önü başka oyuncuyla kapanıyorsa bloklama bunu kendisi açar: önce DURAN gösteren hedeften uzaklaşır, olmuyorsa
    duran öndeki oyuncu kayar (en az kaydırma). Temas olaylı plana, yürüyen oyuncuya ve sağ-sol sırasına dokunmaz. beat['motion']
    yerinde değişir. Dönüş: bloklama notları ('adjusted' | 'unresolved')."""
    motion, notes = beat["motion"], []
    objects = (beat.get("choreo") or {}).get("objects")
    dur = beat["t_end"] - beat["t_start"]
    free = kind in continuity.FREE or not prev_x
    prev = {} if free else {c: float(v) for c, v in prev_x.items() if c in motion}
    heights = {c: designs[c]["height"] for c in motion if c in designs}
    frozen = bool(any(object_state.events(ob.get("track") or []) for ob in objects or []))
    wins = [w for w in windows(beat) if w[2]["by"] in designs]
    for _a, _b, item in wins:
        hidden = hand_hidden(beat, designs, item)
        if not hidden:
            continue
        by = item["by"]
        tb = target_box(beat, designs, item, _a)
        away = 1.0 if sm.motion_x(motion[by], _a, dur, heights[by]) >= tb[0] else -1.0
        options = [] if frozen else [(c, d) for c, d in [(by, (away,))] + [(h, (away, -away)) for h in hidden]
                                     if c not in locked and motion[c]["kind"] not in continuity.MOVING]
        best = None
        for step in range(1, int(round(action_staging.OCCL_SHIFT_MAX / 0.05)) + 1):
            for cid, dirs in options:
                for sg in dirs:
                    cand = action_staging._shifted(motion[cid], sg * 0.05 * step, "mark", prev.get(cid), heights, cid, cid not in prev)
                    if cand is None:
                        continue
                    ap, rc = cand.get("approach"), (react or {}).get(cid)
                    if ap and (ap["walk_s"] > _a or (rc and float(rc["t"]) < ap["walk_s"] - 1e-6)):       # jest başlamadan yerine varır
                        continue
                    trial = dict(motion, **{cid: cand})
                    if any((sm.motion_x(motion[cid], t, dur, heights[cid]) - sm.motion_x(motion[o], t, dur, heights[o]))
                           * (sm.motion_x(cand, t, dur, heights[cid]) - sm.motion_x(motion[o], t, dur, heights[o])) < 0
                           for o in heights if o != cid for t in (0.0, dur)):
                        continue
                    if set(action_staging._blocked_pairs(trial, designs, dur)) - set(action_staging._blocked_pairs(motion, designs, dur)):
                        continue
                    if any(hand_hidden(beat, designs, w[2], trial) for w in wins):
                        continue
                    best = (cid, cand); break
                if best:
                    break
            if best:
                break
        if best is None:
            notes.append({"rule": "blocking", "kind": "unresolved", "actor": by,
                          "why": f"{by} gösterirken eli {', '.join(hidden)} arkasında kalıyor; yer açılamadı: bloklama ya da jestin zamanı yeniden yazılmalı"})
            continue
        cid, cand = best
        old = float(motion[cid]["x0"])
        motion[cid] = cand
        notes.append({"rule": "blocking", "kind": "adjusted", "actor": cid, "intent_x": round(old, 3), "to": round(float(cand["x0"]), 3),
                      "why": f"{by} gösterirken eli {', '.join(hidden)} arkasında kalıyordu: {cid} işareti {old:.2f} → {float(cand['x0']):.2f} m"})
    return notes


def apply(beat, designs, items_, lt):
    """Çizim pozlarına gösterme jestini uygular (yerinde). items_: render2d.frame oyuncu listesi."""
    for a, b, it in windows(beat):
        w = weight(a, b, lt)
        if w <= 0.0:
            continue
        row = next((r for r in items_ if r[0] == it["by"]), None)
        tb = target_box(beat, designs, it, lt)
        if row is None or tb is None:
            continue
        _cid, des, pose = row[0], row[1], row[2]
        dx, h = tb[0] - pose["x"], (tb[1] + tb[2]) / 2
        side = arm_side(des, pose, dx)
        shx, shh = pp.shoulder_offset(des, pose, side)
        vx, vh = dx - shx, h - shh
        dist = max(1e-6, (vx * vx + vh * vh) ** 0.5)
        reach = min(dist, des["height"] * 0.27)                         # kol düz uzanır; hedef yakınsa el hedefi geçmez
        pp.arm_blend(des, pose, side, shx + vx / dist * reach, shh + vh / dist * reach, w)
        other = "L" if side == "R" else "R"
        if ("d" + other) not in pose:                       # öteki el boşsa gösterirken sakinleşir: ikinci bir jest göstermeyle yarışmaz
            rest = (0.0, 0.12 if other == "L" else -0.12)
            pose["a" + other] = [v + (r_ - v) * w for v, r_ in zip(pose["a" + other], rest)]
        if w > 0.5:
            pose["hand"], pose["hand_side"], pose["aim"] = "point", side, side
