"""AHOS 2D kare çizici: plan + poz -> PNG kareleri (çok işlemcili, kaldığı yerden devam)."""
import json, math, multiprocessing, os, shutil, sys, time
from concurrent.futures import ProcessPoolExecutor
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shot_motion as sm  # noqa: E402
import puppet2d as pp  # noqa: E402
import scenes2d as sc  # noqa: E402
import props2d
import object_state  # noqa: E402
import action_staging  # noqa: E402
import setpieces2d  # noqa: E402
import fx_layer  # noqa: E402
try:
    import bg_art  # noqa: E402
except ImportError:      # arka plan boyama katmanı yoksa eski görünüm
    bg_art = None

EMO = {"laugh": "laugh", "surprise": "surprise", "jump": "happy", "dance": "happy", "run": "happy", "wave": "happy"}
BACK_PROPS = ("leaves", "drops")
ZOOM = {"wide": 1.0, "medium": 1.1, "close": 1.6, "xclose": 2.3}


def _prof():
    try:
        import style_profile
        return style_profile.current()
    except Exception:
        return {}


def letter_at(cues, t):
    for c in cues:
        if c[0] <= t < c[1]:
            return c[3] if len(c) > 3 else "C"
    return "X"


def letter_window(cues, lt, frame_dt, lead=0.03):
    """Kare penceresine göre ağız harfi: 12 fps'te kısa görüntü birimleri (viseme) kaçmasın; ağız sesten ~30 ms önce hareket eder (animasyon geleneği)."""
    a, b = lt + lead, lt + lead + frame_dt
    best, bo, bx = None, 0.0, 0.0
    for c in cues:
        ov = min(b, c[1]) - max(a, c[0])
        if ov <= 0:
            continue
        v = c[3] if len(c) > 3 else "C"
        if v == "X":
            bx = max(bx, ov)
        elif ov > bo:
            best, bo = v, ov
    if best is not None and bo >= 0.30 * frame_dt:
        return best
    return "X"


def _hash(*a):
    h = 2166136261
    for v in a:
        h = ((h ^ int(v * 1000) & 0xFFFFFFFF) * 16777619) & 0xFFFFFFFF
    return h / 4294967295.0


def blink_at(t, seed):
    """Düzensiz göz kırpma: ~3,3 sn'de bir, bazen çift."""
    slot = int(t / 0.9)
    ph = (t / 0.9) - slot
    r = _hash(slot, seed)
    return (r < 0.27 and ph < 0.14) or (0.27 <= r < 0.32 and (ph < 0.12 or 0.30 < ph < 0.42))


def emphasis(cues, lt):
    """Açık ünlü (C/D) başlangıçlarında kısa vurgu darbeleri: kafa/kaş/el için."""
    e = 0.0
    for c in cues:
        if len(c) > 3 and c[3] in "CD":
            e += math.exp(-(((lt - c[0]) / 0.13) ** 2))
    return min(1.0, e)



def _x_at(px, cid, m):
    return px.get(cid, m["x1"])


def _tg(beat):
    """Bu planın nesne hedefleri: mekân verisindeki dekor parçalarından türetilmiş (plan['targets']); yoksa boş — motor hedef uydurmaz."""
    return beat.get("targets") or {}


def pick_hand(beat, holder, hand=None):
    """Hangi el tutacak: açık 'hand' varsa o; yoksa vuruşun BAŞLANGIÇ konumlarından (zamandan bağımsız => el sıçramaz): yürüyorsa gidiş yönü, değilse karşıdaki kişiye yakın el."""
    if hand in ("L", "R"):
        return hand
    mo = beat.get("motion") or (beat.get("choreo") or {}).get("motion") or {}; m = mo.get(holder) or {}
    cast = beat.get("cast") or beat.get("characters") or list(mo)
    others = [mo[c]["x0"] for c in cast if c != holder and c in mo]
    tgt_x = None
    for ob in (beat.get("choreo") or {}).get("objects", []):                    # atılacak/bırakılacak hedef varsa tutan el hedefe yakın olan (atış kolu hedefe doğru savrulur)
        tr = ob.get("track") or []
        for a_, b_ in zip(tr, tr[1:]):
            if a_.get("holder") == holder and isinstance(b_.get("at"), str) and b_["at"] in _tg(beat):
                tgt_x = _tg(beat)[b_["at"]][0]
    if tgt_x is not None:
        side = 1.0 if tgt_x > m.get("x0", 0.0) else -1.0
    elif m.get("kind") in ("walk", "carry", "run") and abs(m.get("x1", 0) - m.get("x0", 0)) > 0.05:
        side = 1.0 if m["x1"] > m["x0"] else -1.0
    elif others:
        side = 1.0 if others[0] > m.get("x0", 0.0) else -1.0
    else:
        side = 1.0
    return "R" if side > 0 else "L"


def _hold_pos(cid, items, designs, beat, lt, hand=None, grip=0.12):
    """Nesne TABANININ dünya konumu: çizilen elin gerçek yeri (pp.hand_offset) eksi tutuş yüksekliği (nesne elin içinde, el tutuş noktasında)."""
    for cid_, d_, p_, m_, _lk, _e in items:
        if cid_ == cid:
            dx, h = pp.hand_offset(d_, p_, pick_hand(beat, cid, hand))
            return p_["x"] + dx, max(0.0, h - grip), d_["height"]
    return None


def object_owner(st):
    """Çizim sırası için nesnenin o an hangi karaktere ait çizildiği (None = serbest: yerde/uçuşta)."""
    s = st["state"]
    if s == "held":
        return st["holder"]
    if s == "transfer":
        return st["holder"] if st["u"] < 0.5 else st["to"]
    if s == "put":
        return st["holder"] if st["u"] < 0.5 else None
    if s == "pickup":
        return st["to"] if st["u"] >= 0.5 else None
    return None


def _objects_now(beat, items, lt):
    """[(ob, x, y, state, owner, hand)] — her nesne için konum (tutuş noktası dahil) ve çizim sahibi."""
    out = []
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        sc = ob.get("scale", 0.55); grip = object_state.grip_of(ob["prop"], sc)
        def hold(holder, t_, hand=None, _g=grip):
            h = _hold_pos(holder, items, None, beat, t_, hand, _g)
            return (h[0], h[1]) if h else (0.0, 0.0)
        def target(at):
            at = _tg(beat)[at] if isinstance(at, str) else at
            return (at[0], at[1])
        x, y, st = object_state.position(tr, lt, hold, target)
        if x is None:
            continue                                            # imha (açık hide olayı, yalnız tanımlı hedefte): kutunun ağzında asılı kalmaz
        own = object_owner(st)
        out.append((ob, x, y, st, own, pick_hand(beat, own) if own else None))
    return out


def _draw_objects(cv, cam, beat, items, designs, lt, owner="__free__", emit=None):
    """Nesneleri çizer. owner='__free__': serbest nesneler (yerde, uçuşta); owner=cid: o karakterin elindekiler (karakterden HEMEN sonra, parmaklar önde)."""
    by = {i[0]: i for i in items}
    for ob, x, y, st, own, hand in _objects_now(beat, items, lt):
        late = st["state"] == "transfer"                        # el değiştirirken nesne iki karakterin de ÖNÜNDE (alıcı karakter vericiyi örtüp nesneyi gizlemesin)
        slot = "__late__" if late else ("__free__" if own is None else own)
        if slot != owner:
            continue
        body = lambda c, cm, o_=ob, x_=x, y_=y: props2d.draw(c, cm, o_["prop"], x_, y_, 0.0, 0, scale=o_.get("scale", 0.55))
        body(cv, cam)
        if emit is not None:
            emit("object", ob.get("id") or ob.get("prop", "obj"), body, (x, y))
        if own is not None and own in by:                       # parmaklar nesnenin ÖNÜNDE: avuç nesneyi kavrar
            _c, d_, p_, _m, _l, _e = by[own]
            grip_ = lambda c, cm, d2=d_, p2=p_, h2=hand: pp.draw_grip(c, d2, p2, h2, cm.x(p2["x"]), cm.y(0.0), cm.s)
            grip_(cv, cam)
            if emit is not None:
                emit("grip", own, grip_)


def object_effects(beat, cid, lt):
    """Nesne olaylarından oyuncu etkisi: (uzanma yerel zamanı, uzanma süresi) veya None; ve taşınan ağırlık (kg-benzeri) -> poz farkı.
    Alma/verme/bırakma'da karakter temastan ÖNCE uzanır (hazırlık), temas anında kol en uzakta (tepe)."""
    reach = None; weight = 0.0
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        for w in object_state.reach_windows(tr):
            if w["actor"] == cid and w["t0"] <= lt <= w["t1"] + (w["t1"] - w["t0"]):
                reach = (lt - w["t0"], 2.0 * max(0.3, w["t1"] - w["t0"]))
        st = object_state.state_at(tr, lt)
        if st["state"] in ("held", "put") and st["holder"] == cid or (st["state"] == "transfer" and cid in (st["holder"], st["to"])):
            weight = max(weight, object_state.weight_of(ob.get("prop")))
    return reach, weight


def handoff_problems(plan, designs):
    """Planlama ön kontrolü: her EL DEĞİŞTİRME için iki karakterin kolu buluşma noktasına yetişiyor mu? Yetişmiyorsa plana geri bildirilir
    (yaklaşma ekle ya da atma olarak tanımla); motor eli sessizce 'ışınlamaz'."""
    probs = []
    for b in plan.get("beats", []):
        mo = b.get("motion") or {}; dur = b["t_end"] - b["t_start"]
        for oi, ob in enumerate((b.get("choreo") or {}).get("objects", [])):
            for e in object_state.events(ob.get("track") or []):
                if e["type"] != "handoff" or e["by"] not in mo or e["to"] not in mo or e["by"] not in designs or e["to"] not in designs:
                    continue
                xs = {}
                for c in (e["by"], e["to"]):
                    xs[c] = sm.motion_x(mo[c], e["t"], dur, designs[c]["height"])
                ratio = pp.handoff_reach_ratio(designs[e["by"]], xs[e["by"]], designs[e["to"]], xs[e["to"]], pick_hand(b, e["by"]), pick_hand(b, e["to"]))
                if ratio > 1.0:
                    probs.append("vuruş %s nesne %d: %s -> %s el değiştirme t=%.1f: kollar buluşamıyor (erişim oranı %.2f, x=%.2f/%.2f); karakterler yaklaşmalı veya atma olarak tanımlanmalı"
                                 % (b.get("id", "?"), oi, e["by"], e["to"], e["t"], ratio, xs[e["by"]], xs[e["to"]]))
    return probs


CROUCH_DOWN_S, CROUCH_UP_S, CROUCH_MIN_S = 0.9, 0.9, 0.45      # çömelme / doğrulma süresi ve sıkışınca en kısa süre (sn)


def _walk_end(m, dur):
    """Plan içinde yürüyüşün bittiği an (yürümüyorsa 0)."""
    if m.get("approach"):
        return 0.85 * float(m["approach"]["walk_s"])
    if m.get("kind") in ("walk", "carry", "run") and abs(m.get("x1", m.get("x0", 0)) - m.get("x0", 0)) > 0.05:
        return 0.85 * float(m.get("walk_s") or dur)
    return 0.0


def crouch_times(beat, e):
    """El değiştirme çömelmesinin zamanları (vuruş içi sn): (iniş başı, iniş sonu, doğrulma başı, doğrulma sonu).
    Yürüyen oyuncu varmadan çömelmeye başlamaz (süre yetmiyorsa en kısa süre korunur); plan sınırı dışına taşmaz."""
    dur = beat["t_end"] - beat["t_start"]; mo = beat.get("motion") or {}
    down_end = max(e["t_start"] + 0.1, CROUCH_MIN_S)
    walked = max((_walk_end(mo[c], dur) for c in (e["by"], e["to"]) if c in mo), default=0.0)
    down0 = max(0.0, min(max(down_end - CROUCH_DOWN_S, walked), down_end - CROUCH_MIN_S))
    up0 = max(down_end, e["t"] + 0.2)
    up1 = max(up0 + CROUCH_MIN_S, min(up0 + CROUCH_UP_S, dur))
    return down0, down_end, up0, up1


def crouch_envelope(beat, e, lt):
    a, b, c, d = crouch_times(beat, e)
    if lt <= a or lt >= d:
        return 0.0
    if lt < b:
        return pp_smooth((lt - a) / (b - a))
    if lt <= c:
        return 1.0
    return 1.0 - pp_smooth((lt - c) / (d - c))


def apply_handoff_reach(beat, items, lt):
    """El değiştirme penceresinde iki karakterin kolu buluşma noktasına uzanır (yönlü uzanma). Zarf: yaklaşma -> tutma -> bırakma."""
    by = {i[0]: i for i in items}
    for ob in (beat.get("choreo") or {}).get("objects", []):
        for e in object_state.events(ob.get("track") or []):
            if e["type"] != "handoff" or e["by"] not in by or e["to"] not in by:
                continue
            ts, tc = e["t_start"], e["t"]; D = max(0.2, tc - ts)
            t0, t1 = ts - 0.4, tc + 0.4
            c0, _c1, _c2, c3 = crouch_times(beat, e)
            if not (min(t0, c0) <= lt <= max(t1, c3)):
                continue
            if not (t0 <= lt <= t1):
                w = 0.0                                          # yalnız çömelme sürüyor: kollar henüz/artık eylem pozunda
            elif lt < ts + 0.3 * D:
                w = pp_smooth((lt - t0) / (0.4 + 0.3 * D))
            elif lt <= tc - 0.3 * D:
                w = 1.0
            else:
                w = 1.0 - pp_smooth((lt - (tc - 0.3 * D)) / (0.3 * D + 0.4))
            ga, ra = by[e["by"]], by[e["to"]]
            xg, xr = ga[2]["x"], ra[2]["x"]
            sg_, sr_ = pick_hand(beat, e["by"]), pick_hand(beat, e["to"])
            wc = crouch_envelope(beat, e, lt)                    # boy farkı: omzu yüksek olan gerçekten çömelir (buluşma noktası alçalır, baş kısa olanınkine yaklaşır)
            for who, drop in zip((ga, ra), pp.kneel_drops(ga[1], ra[1])):
                if drop > 0.0 and wc > 0.0:
                    who[2]["crouch"] = max(who[2].get("crouch", 0.0), drop * wc); who[2]["head"][0] += 0.12 * wc * min(1.0, drop / (0.1 * who[1]["height"]))
            gx, gh = pp.shoulder_offset(ga[1], ga[2], sg_); rx, rh = pp.shoulder_offset(ra[1], ra[2], sr_)
            span = 2.0 * object_state.grip_of(ob.get("prop", ""), ob.get("scale", 0.55))          # kavrama noktası nesnenin ortası sayılır
            ha_, hb_ = pp.grip_points(ga[1], (xg + gx, gh), ra[1], (xr + rx, rh), span)
            for (cid, des, p, *_), side, xs_, (mx, mh) in ((ga, sg_, xg, ha_), (ra, sr_, xr, hb_)):
                if w <= 0.0 or pp.view_of(p) == "side":
                    continue
                old = list(p["aL"]) if side == "L" else list(p["aR"])
                pp.arm_toward(des, p, side, mx - xs_, mh)
                key = "aL" if side == "L" else "aR"
                p[key] = [old[0] + (p[key][0] - old[0]) * w, old[1] + (p[key][1] - old[1]) * w]


def apply_throw_swing(beat, items, lt):
    """Atış/bırakma kolu: bırakmadan önce geri salınım, bırakma anında hedefe doğru ileri savurma (kol nesneyi gerçekten fırlatır), sonra gevşeme."""
    by = {i[0]: i for i in items}
    for ob in (beat.get("choreo") or {}).get("objects", []):
        for e in object_state.events(ob.get("track") or []):
            if e["type"] not in ("dispose", "drop") or e["by"] not in by:
                continue
            ts = e["t_start"]; tgt = None
            for k in ob["track"]:
                if isinstance(k.get("at"), str) and k["t"] == e["t"]:
                    tgt = _tg(beat).get(k["at"])
            if tgt is None or not (ts - 0.45 <= lt <= ts + 0.5):
                continue
            cid, des, p, *_ = by[e["by"]]
            if pp.view_of(p) == "side":
                continue
            side = pick_hand(beat, cid); dirn = 1.0 if tgt[0] >= p["x"] else -1.0
            sx, sh = pp.shoulder_offset(des, p, side); ln = des["height"] * 0.27
            if lt < ts - 0.1:
                w = pp_smooth((lt - (ts - 0.45)) / 0.35); tx, th = sx - dirn * 0.5 * ln, sh - 0.9 * ln       # geri salınım (aşağı-geri)
            elif lt <= ts + 0.15:
                w = 1.0; u = pp_smooth((lt - (ts - 0.1)) / 0.25); tx = sx + dirn * (-0.5 + 1.5 * u) * ln; th = sh - (0.9 - 1.3 * u) * ln   # ileri-yukarı savurma
            else:
                w = 1.0 - pp_smooth((lt - (ts + 0.15)) / 0.35); tx, th = sx + dirn * 1.0 * ln, sh + 0.4 * ln
            key = "aL" if side == "L" else "aR"; old = list(p[key])
            pp.arm_toward(des, p, side, tx, th)
            p[key] = [old[0] + (p[key][0] - old[0]) * w, old[1] + (p[key][1] - old[1]) * w]


def pp_smooth(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


def carry_info(beat, cid, lt):
    """Karakter şu an bir nesne taşıyorsa {'prop','weight','style','hand','reach'} (ağırlık merkezi: yük gövdeden ne kadar önde), yoksa None."""
    best = None
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        st = object_state.state_at(tr, lt)
        mine = (st["state"] in ("held", "put") and st["holder"] == cid) or (st["state"] == "transfer" and cid in (st["holder"], st["to"]))
        if not mine:
            continue
        w = object_state.weight_of(ob["prop"])
        if best is None or w > best["weight"]:
            sty = object_state.carry_style(ob["prop"])
            best = {"prop": ob["prop"], "weight": w, "style": sty, "hand": pick_hand(beat, cid),
                    "reach": 0.25 if sty == "two_hand_front" else 0.15}
    return best


def _head_cropped(cam, x, H):
    """Başın/saçın/omzun ekran sınırında KISMEN kesilip kesilmediği (tamamen içerde/tamamen dışarıda sorun değil).
    Çocukta baş büyük (çene ~0.50H), yetişkinde çene ~0.70H; alt kenarda ön plan çimi (y>640) yüzü örter."""
    hw = 0.30 * H * cam.s; cx = cam.x(x); top = cam.y(H * 1.02); bot = cam.y(H * (0.50 if H < 1.3 else 0.70))
    inside_x = (cx - hw >= 0) and (cx + hw <= 1280)
    outside_x = (cx + hw <= 0) or (cx - hw >= 1280)
    inside_y = (top >= 0) and (bot <= 640)
    outside_y = bot <= 0 or top >= 720
    return not ((inside_x and inside_y) or outside_x or outside_y)

REACT_AFTER = 1.0      # replik bittikten sonra dinleyene kesme süresi (sn)
REACT_MID = 0.9        # uzun replikin ortasında tepki süresi (sn)
REACT_MIN_LINE = 3.0   # bu süreden uzun replikte orta tepki


def reaction_target(beat, t):
    """Tepki planında kamera kimde olmalı? Yalnız >1 karakter varsa; konuşan olmayan (dinleyen) karakter döner, yoksa None."""
    cast = beat.get("cast") or []
    if len(cast) < 2 or not beat.get("lines"):
        return None
    lines = beat["lines"]
    for ln in lines:
        d = ln["end"] - ln["start"]
        others = [c for c in cast if c != ln["char"]]
        if not others:
            continue
        if ln["end"] <= t < ln["end"] + REACT_AFTER and not any(l["start"] <= t < l["end"] for l in lines):
            return others[0]                              # replik bitti, kimse konuşmuyor: dinleyen yüz
        mid = ln["start"] + 0.62 * d
        if d >= REACT_MIN_LINE and mid <= t < mid + REACT_MID:
            return others[0]                              # uzun replikte araya tepki
    return None


def frame(plan, designs, t, bible_chars=None, trace=None):
    """trace (dict) verilirse çizimin GERÇEK yerleşimi yazılır: kamera, pozlar ve çizim sırasıyla katmanlar [(tür, kimlik, çizici(cv, cam), nokta)].
    Okunabilirlik ölçüsü bu kayıttan çalışır; ayrı bir yerleşim tahmini yapılmaz."""
    beat = next((b for b in plan["beats"] if b["t_start"] <= t < b["t_end"]), None)
    if beat is None:
        return None
    lt, dur = t - beat["t_start"], beat["t_end"] - beat["t_start"]
    speaker, letters = None, {}
    spk_mood = {}
    for ln in beat["lines"]:
        if ln["start"] <= t < ln["end"]:
            speaker = ln["char"]
            spk_mood[ln["char"]] = ln.get("mood", "neutral")
            letters[ln["char"]] = letter_window(ln["cues"], t - ln["start"], 1.0 / float(plan.get("fps", 12))) if ln["cues"] else "CBDX"[int(t * 9) % 4]
    items, xs = [], []
    sp_cues = next((ln["cues"] for ln in beat["lines"] if ln["char"] == speaker and ln["start"] <= t < ln["end"]), [])
    sp_start = next((ln["start"] for ln in beat["lines"] if ln["char"] == speaker and ln["start"] <= t < ln["end"]), 0)
    E = emphasis(sp_cues, t - sp_start) if speaker else 0.0
    px = {}
    for cid in beat["cast"]:
        px[cid] = sm.motion_x(beat["motion"][cid], lt, dur, designs[cid]["height"])
    for cid in beat["cast"]:
        m, d = beat["motion"][cid], designs[cid]
        Hm = d["height"]
        rc = ((beat.get("choreo") or {}).get("react") or {}).get(cid)           # yönetmen tepkisi: belirli andan sonra (ör. şaşırma)
        m, seg_t, seg_d = sm.segment(m, lt, dur)             # yaklaşma yürüyüşü varsa o parça; yoksa eylemin kendisi
        lte, kind_e = seg_t, m["kind"]
        if rc and lt >= float(rc["t"]):
            lte, kind_e = lt - float(rc["t"]), rc["kind"]
            m = dict(m); m["kind"] = kind_e; m["x0"] = m["x1"] = _x_at(px, cid, m); seg_d = dur
        reach_w, carry_w = object_effects(beat, cid, lt)
        dur_e = seg_d
        if reach_w and kind_e in ("idle", "look") and not rc:      # nesne teması yaklaşıyor ve karakter boşta: uzanma hazırlığı otomatik
            lte, dur_e, kind_e = reach_w[0], reach_w[1], "reach"
            m = dict(m); m["kind"] = "reach"; m["x0"] = m["x1"] = _x_at(px, cid, m)
        args = (kind_e, 0, dur_e, m["seed"], m["x0"], m["x1"], Hm, Hm * 0.45)
        spk = (cid == speaker)
        p = sm.pose_at(args[0], lte, *args[2:], speaking=spk)
        # takip (follow-through): kollar gövdeden, kafa da biraz geriden gelir
        pa = sm.pose_at(args[0], max(0.0, lte - 0.11), *args[2:], speaking=spk)
        ph_ = sm.pose_at(args[0], max(0.0, lte - 0.05), *args[2:], speaking=spk)
        p["aL"], p["aR"], p["head"] = list(pa["aL"]), list(pa["aR"]), list(ph_["head"])
        ci = carry_info(beat, cid, lt)
        if ci:                                                     # taşıma: ağırlık + taşıma biçimi (yük önde/yanda/omuzda) -> denge, kol pozu
            adj = object_state.carry_adjust(ci["weight"], ci["style"], ci["reach"])
            p["lean"] += adj["lean"]; p["sq"] = p.get("sq", 1.0) + adj["sq"]; p["head"][0] += adj["head_nod"]
            if kind_e != "reach":                                  # tepki (şaşırma/gülme) sırasında da tutan kol nesneyi taşımaya devam eder
                ha = "aL" if ci["hand"] == "L" else "aR"; sg_ = 1 if ci["hand"] == "L" else -1
                if adj["arms"] == "both_front":
                    for a_ in ("aL", "aR"):
                        p[a_][0] = -0.95
                    p["aL"][1] = 0.30; p["aR"][1] = -0.30
                elif adj["arms"] == "one_up":
                    p[ha][0] = -0.40; p[ha][1] = sg_ * 1.6
                else:
                    p[ha][0] = -0.35; p[ha][1] = sg_ * 0.25
                    p["head"][1] += -sg_ * adj["side_tilt"]
                    stationary_ = (kind_e not in ("walk", "carry", "run")) or (kind_e == "walk" and (abs(m["x1"] - m["x0"]) < 0.02 or lt >= 0.9 * seg_d))      # yürüyüp varmış karakter de duran sayılır
                    if stationary_ and ci["weight"] < 1.5 and ci["style"] != "two_hand_front":
                        # duran kişi hafif nesneyi kalça hizasında sallamaz: dirseği bükük, nesne göğüs hizasında önde tutar (boy ve kola göre; çocuk yüzüyle aynı hizaya düşmez)
                        gz_ = ((beat.get("choreo") or {}).get("gaze") or {}).get(cid)
                        dn = (1.0 if px[gz_] > px[cid] else -1.0) if gz_ in px and gz_ != cid else (1.0 if ci["hand"] == "R" else -1.0)
                        ln_ = Hm * 0.27; shx_, shh_ = pp.shoulder_offset(d, p, ci["hand"])
                        pp.arm_toward(d, p, ci["hand"], shx_ + dn * 0.12 * ln_, shh_ - 0.20 * ln_)
        look = 0.0
        gz = ((beat.get("choreo") or {}).get("gaze") or {}).get(cid)       # yönetmen bakışı: konuşulan kişiye/nesneye
        if gz in px and gz != cid:
            look = 1.0 if px[gz] > px[cid] else -1.0
            p["head"][2] += 0.8 * look
        elif speaker and cid != speaker and speaker in px:            # dinleyen konuşana bakar
            look = 1.0 if px[speaker] > px[cid] else -1.0
            p["head"][2] += 0.7 * look
        if spk:                                                      # vurgulu hecede baş, kaş, el
            p["head"][0] += 0.14 * E
            p["z"] += 0.012 * Hm * E
            p["aR"][1] = (p["aR"][1] if p["aR"][1] else -0.2) - 0.5 * E
        items.append((cid, d, p, m, look, E if spk else 0.0))
        xs.append(p["x"])
    apply_throw_swing(beat, items, lt)                   # atışta kol savurma
    apply_handoff_reach(beat, items, lt)                 # el değiştirmede eller buluşma noktasına uzanır
    avg = sum(xs) / len(xs) if xs else 0.0
    focus = beat.get("focus")
    reaction = reaction_target(beat, t)               # tepki planı: replik bitince / uzun replikin ortasında dinleyene kesilir
    if reaction:
        focus = reaction
    elif speaker and speaker in beat["cast"]:       # yakın planda kamera hep o an konuşana bakar (yüz + omuz kadrajda)
        focus = speaker
    fh = designs[focus]["height"] if focus in designs else 1.1
    fx = xs[beat["cast"].index(focus)] if focus in beat["cast"] else avg
    SUB = 3.5                                          # kurgu: uzun vuruş 3,5 sn'lik çekimlere bölünür (kesme)
    sub = int(lt / SUB) if dur > 5.0 else 0
    ph = ((lt % SUB) / SUB) if dur > 5.0 else lt / max(dur, 0.1)
    preset = beat["camera"]
    if sub > 0:
        preset = ("wide", "medium", "close", "wide")[(int(beat.get("i", 0)) + sub) % 4]
        if beat.get("props") and sub % 2 == 0:
            preset = "insert"
    if lt < 1.4 and any(m_["kind"] == "surprise" for m_ in beat["motion"].values()):
        preset = "xclose"                               # şaşırma anında aşırı yakın plan (yüz dolsun)
    if reaction:
        preset = "close"                                # tepki planı her zaman yakın plan
    if speaker and speaker in beat["cast"] and preset in ("close", "xclose") and not reaction:
        fx = xs[beat["cast"].index(speaker)]
    zoom = ZOOM.get(preset, 1.5) * (1.0 + 0.05 * ph) * (1.0 + 0.18 * E if preset == "close" else 1.0)   # vurguda kamera içeri vurur
    if preset in ("close", "xclose") and focus in designs and designs[focus]["height"] > 1.3:
        zoom *= 0.78                                    # yetişkin yakın planda ekranı doldurmasın: kadraj biraz açılır
    cx = fx if preset in ("close", "xclose") else avg
    cy = {"wide": 0.95, "medium": min(0.85, fh * 0.62 + 0.25)}.get(preset, fh * 0.80)   # orta planda çocuk için kamera alçalır (bacak değil gövde+yüz)
    if preset in ("wide", "medium") and len(xs) > 1:            # kadraj güvenliği: tüm oyuncular kadraja sığsın
        lo, hi = min(xs), max(xs); half = (hi - lo) / 2 + 0.7
        zoom = max(0.8, min(zoom, 5.12 / (2 * half))); cx = (lo + hi) / 2
    cam = sc.Cam(cx, cy, zoom)
    if preset == "insert" and beat.get("props"):
        ix, iy = props2d.place(beat["props"][0], xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
        cam = sc.Cam(ix, max(0.55, min(iy - 0.35, 1.0)), 1.05)      # ek plan: nesne + karakterler birlikte kadrajda (başsız/bacaksız kadraj yok)
    act_ = action_staging.framing(beat, designs, lt, sc.BASE_PPM)      # temas penceresi: sabit aksiyon kadrajı (tepki/yakın plan/ek plan kesmesi yapılmaz)
    if act_:
        preset = "action"; cam = sc.Cam(act_["cx"], act_["cy"], act_["zoom"])
    cv = pp.Cv()
    layers = [] if trace is not None else None
    emit = (lambda kind_, key_, fn_, at_=None: layers.append((kind_, key_, fn_, at_))) if trace is not None else None
    sc.scene_back(cv, beat["scene"], cam, t, light=beat.get("light", ""))
    if preset != "insert":
        setpieces2d.draw(cv, cam, beat.get("loc"), t, pieces=beat.get("pieces"))
    if bg_art is not None:
        try:
            bg_art.enhance(cv, beat["scene"], beat.get("light"), t)
        except Exception:      # boyama katmanı kare üretimini asla düşürmesin
            pass
    for cid_, d_, p_, m_, _lk, _e in items:                          # koşu/yürüyüş: ayak tozu + hız çizgisi
        if _prof().get("dust", True) and m_["kind"] in ("walk", "run") and lt / max(dur, 0.1) < 0.85 and abs(m_["x1"] - m_["x0"]) > 0.05:
            fx_layer.dust(cv, cam, p_["x"], 1.0 if m_["x1"] >= m_["x0"] else -1.0, t, m_["kind"] == "run", d_["height"])
    for k_, kind in enumerate(beat.get("props") or []):             # arka katman nesneleri (yaprak, damla) karakterlerden ÖNCE çizilir: yüzlerin üstüne binmez
        if kind in BACK_PROPS and preset != "insert":
            wx, wy = props2d.place(kind, xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
            props2d.draw(cv, cam, kind, wx, wy, t, k_)
    act_ids_ = {c for ev_ in action_staging._events(beat) for c in (ev_["by"], ev_.get("to")) if c} if act_ else set()
    for cid, d, p, m, look, e in action_staging.draw_order(beat, designs, items):
        if ((preset in ("close", "xclose") and cid != focus) or (preset == "action" and cid not in act_ids_)) and _head_cropped(cam, p["x"], d["height"]):
            continue                                        # yakın planda odak dışı karakterin yüzü kenarda yarım kesilecekse çizilmez (kazara kesik yüz yok)
        emo = EMO.get(m["kind"], "neutral")
        mood_ = spk_mood.get(cid) or beat.get("mood", "neutral")
        if emo == "neutral" and mood_ != "neutral":
            emo = mood_
        slot = int(t / 1.6 + m["seed"])
        dart = (_hash(slot, m["seed"], 3) - 0.5) * 1.4
        st = {"mouth": letters.get(cid, "X"), "blink": blink_at(t, m["seed"]), "emotion": emo,
              "gaze": look * 0.9 + (0 if look else dart), "brow": e, "pulse": e}
        body_ = lambda c, cm, d_=d, p_=p, st_=st: pp.draw_character(c, d_, p_, st_, cm.x(p_["x"]), cm.y(0.0), cm.s, t)
        body_(cv, cam)
        if emit is not None:
            emit("character", cid, body_, (p["x"], 0.0))
        _draw_objects(cv, cam, beat, items, designs, lt, owner=cid, emit=emit)      # elindeki nesne: karakterden hemen sonra, parmaklar önde
    if xs:
        fx_layer.icons(cv, cam, beat, xs, [designs[c]["height"] for c in beat["cast"]], t, lt)
    _draw_objects(cv, cam, beat, items, designs, lt, emit=emit)             # serbest nesneler (yerde, uçuşta)
    _draw_objects(cv, cam, beat, items, designs, lt, owner="__late__", emit=emit)   # el değiştiren nesne: tüm karakterlerden sonra
    for k_, kind in enumerate(beat.get("props") or []):
        if kind in BACK_PROPS:
            continue
        wx, wy = props2d.place(kind, xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
        props2d.draw(cv, cam, kind, wx, wy, t, k_)
    if xs:
        hy = max(designs[c]["height"] for c in beat["cast"]) * 1.1
        for kind in beat.get("fx") or []:
            if kind == "speed":      # eski üst-katman hız çizgisi yüzlerin üstüne biniyordu; yerine fx_layer.dust (arkada) var
                continue
            props2d.draw_fx(cv, cam, kind, sum(xs) / len(xs), hy if kind != "speed" else 0.1, t, lt)
    sc.scene_front(cv, beat["scene"], cam, t)
    if trace is not None:
        emit("front", "scene_front", lambda c, cm: sc.scene_front(c, beat["scene"], cm, t))
        trace.update(cam=cam, preset=preset, items=items, layers=layers, beat=beat, lt=lt)
    im = grade(cv.done(), beat.get("light") or "", t)
    try:
        return fx_layer.post(im, beat, t, lt, dur, float(plan.get("total_s", 480.0)), bool(beat.get("first_of_scene")))
    except Exception:          # efekt katmanı asla kare üretimini düşürmesin
        return im


_VIG = {}


def grade(im, light, t):
    """Işık/atmosfer: sahne ışığına göre renk tonu + hafif vinyet (derinlik hissi). Yazıdaki ışık notundan türetilir."""
    from PIL import Image, ImageChops
    l = str(light).lower()
    if any(k in l for k in ("gün batım", "akşam", "altın", "kızıl")):
        tint, k = (255, 200, 150), 0.30
    elif any(k_ in l for k_ in ("sabah", "doğu")):
        tint, k = (255, 232, 200), 0.22
    elif any(k_ in l for k_ in ("bulut", "kapalı", "gölge")):
        tint, k = (215, 225, 245), 0.20
    elif any(k_ in l for k_ in ("öğle", "güneşli", "parlak")):
        tint, k = (255, 248, 230), 0.10
    else:
        tint, k = (255, 245, 225), 0.12
    sz = im.size
    tinted = ImageChops.multiply(im, Image.new("RGB", sz, tint))
    im = Image.blend(im, tinted, k)
    m = _VIG.get(sz)
    if m is None:
        w, h = sz; small = Image.new("L", (64, 36), 255)
        px = small.load()
        for y in range(36):
            for x in range(64):
                d = (((x - 31.5) / 32) ** 2 + ((y - 17.5) / 18) ** 2) ** 0.5
                px[x, y] = int(255 - 70 * max(0.0, d - 0.55) / 0.9)
        m = _VIG[sz] = small.resize(sz, Image.BILINEAR)
    return ImageChops.multiply(im, Image.merge("RGB", (m, m, m)))


_G = {}
ENGINE_FILES = ("render2d.py", "puppet2d.py", "scenes2d.py", "setpieces2d.py", "props2d.py", "fx_layer.py", "bg_art.py", "shot_motion.py", "puppet_side.py", "object_state.py",
                "shot_planner.py", "style_profile.py", "mood_engine.py", "action_staging.py", "staging.py", "continuity.py")


def available_mem_mb():
    """Kullanılabilir RAM (MB). Windows: GlobalMemoryStatusEx; Linux: /proc/meminfo. Okunamazsa None."""
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.ap / 1048576)
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable:"):
                return int(ln.split()[1]) // 1024
    except Exception:
        pass
    return None


def pick_workers(requested=None, per_worker_mb=450, reserve_mb=1200, mem_mb="auto"):
    """İşçi sayısı = min(istenen/CPU-1, (boş RAM - rezerv) / işçi başı RAM), en az 1. AHOS_RENDER_WORKERS ortam değişkeni zorlar (1 = güvenli tek işçi yolu)."""
    env = os.environ.get("AHOS_RENDER_WORKERS", "").strip()
    if env.isdigit() and int(env) >= 1:
        return int(env)
    cap = requested or max(1, (os.cpu_count() or 2) - 1)
    mem = available_mem_mb() if mem_mb == "auto" else mem_mb
    if mem is None:
        return max(1, min(cap, 2))                      # bellek bilinmiyorsa temkinli
    return max(1, min(cap, int((mem - reserve_mb) // per_worker_mb)))


def engine_stamp(plan, designs, fps):
    """Önbellek damgası: motor kaynakları + karakter tasarımları + plan vuruşları + fps + üslup profili. Değişirse eski kareler kullanılmaz."""
    import hashlib
    h = hashlib.sha256()
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in ENGINE_FILES:
        p = os.path.join(here, fn)
        if os.path.exists(p):
            h.update(fn.encode()); h.update(open(p, "rb").read())
    h.update(json.dumps(designs, sort_keys=True, default=str).encode())
    h.update(json.dumps(plan.get("beats", []), sort_keys=True, default=str).encode())
    h.update(str(fps).encode()); h.update(os.environ.get("AHOS_STYLE", "").encode())
    return h.hexdigest()[:16]


def valid_png(path, size=(1280, 720)):
    try:
        if os.path.getsize(path) < 2000:
            return False
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.size == size
    except Exception:
        return False


def _init(plan, designs):
    _G["plan"], _G["des"] = plan, designs


def _work(args):
    """Kareyi geçici dosyaya yaz, doğrula, sonra nihai adına taşı (yarım/bozuk kare tamamlanmış sayılmaz)."""
    f, path, fps = args
    if valid_png(path):
        return 0
    if os.environ.get("AHOS_TEST_FAULT") and multiprocessing.current_process().name != "MainProcess":   # yalnız testler: gerçek işçi ölümü / takılma
        if os.environ["AHOS_TEST_FAULT"] == "crash":
            os._exit(3)
        if os.environ["AHOS_TEST_FAULT"] == "hang":
            time.sleep(60)
    im = frame(_G["plan"], _G["des"], f / float(fps))
    if im is None:
        return 0
    tmp = path + ".tmp.png"
    im.save(tmp)
    if not valid_png(tmp, im.size):
        raise RuntimeError("kare doğrulanamadı: %s" % path)
    os.replace(tmp, path)
    return 1


def _acquire_lock(out_dir, stale_s=1200):
    """Aynı sahne için ikinci çakışan iş başlatma. Başkasının canlı kilidini ASLA kırmaz/sonlandırmaz; yalnız bayat (kalp atışı yok) kilidi devralır."""
    lp = os.path.join(out_dir, ".render.lock")
    if os.path.exists(lp):
        try:
            j = json.load(open(lp, encoding="utf-8"))
        except Exception:
            j = {}
        if time.time() - float(j.get("beat", 0)) < stale_s:
            raise RuntimeError("AYNI SAHNE İÇİN BAŞKA İŞ ÇALIŞIYOR (pid=%s, %s). İkinci iş başlatılmadı; o işi kimliğini doğrulamadan sonlandırmıyorum." % (j.get("pid"), j.get("started")))
    json.dump({"pid": os.getpid(), "started": time.strftime("%H:%M:%S"), "beat": time.time()}, open(lp, "w", encoding="utf-8"))
    return lp


def _beat_lock(lp):
    try:
        j = json.load(open(lp, encoding="utf-8")); j["beat"] = time.time()
        json.dump(j, open(lp, "w", encoding="utf-8"))
    except Exception:
        pass


def render_window(plan, designs, out_dir, workers=None, progress=True, frame_timeout=240, window_mult=3):
    """Dayanıklı render: bellek-duyarlı işçi sayısı, sınırlı kuyruk (parça parça), kare zaman aşımı, çöken işçide yeniden deneme (az işçiyle,
    en sonunda tek işçi), atomik kare yazımı, motor/varlık değişince bayat kare karantinası, kilit + iptal dosyası (.cancel)."""
    from concurrent.futures import wait, FIRST_COMPLETED
    from concurrent.futures.process import BrokenProcessPool
    os.makedirs(out_dir, exist_ok=True)
    fps = plan["fps"]
    f0, f1 = int(round(plan["t0"] * fps)), int(round(plan["t1"] * fps))
    jobs = [(f, os.path.join(out_dir, "f%05d.png" % f), fps) for f in range(f0, f1)]
    lock = _acquire_lock(out_dir)
    t0 = time.time(); done = 0; stats = {"retries": 0, "stale_moved": 0, "timeouts": 0, "cancelled": False}
    try:
        stamp = engine_stamp(plan, designs, fps); sp = os.path.join(out_dir, "_stamp_%d_%d.json" % (f0, f1))
        old = json.load(open(sp, encoding="utf-8")).get("stamp") if os.path.exists(sp) else None
        existing = [j for j in jobs if os.path.exists(j[1])]
        if existing and old != stamp:                       # motor/varlık/plan değişti (veya damga yok): eski kareleri körlemesine kullanma
            qd = out_dir + "_stale_" + time.strftime("%H%M%S"); os.makedirs(qd, exist_ok=True)
            for j in existing:
                os.replace(j[1], os.path.join(qd, os.path.basename(j[1])))
            stats["stale_moved"] = len(existing)
        json.dump({"stamp": stamp, "fps": fps, "created": time.strftime("%Y-%m-%d %H:%M:%S")}, open(sp, "w", encoding="utf-8"))
        for fn in os.listdir(out_dir):                      # yarım kalmış geçici dosyalar
            if fn.endswith(".tmp.png"):
                os.replace(os.path.join(out_dir, fn), os.path.join(out_dir, fn + ".bad"))
        need_n = len([j for j in jobs if not valid_png(j[1])])
        sizes = [os.path.getsize(j[1]) for j in jobs[:200] if os.path.exists(j[1])][:30]
        avg = (sum(sizes) / len(sizes)) if sizes else 1.3e6                  # ölçülmüş kare boyutu yoksa 1,3 MB varsay
        need = int(need_n * avg * 1.3 + 200e6)                                # %30 pay + klip/geçici dosya payı
        free = shutil.disk_usage(out_dir).free
        stats["disk_free_mb"] = int(free / 1e6); stats["disk_need_mb"] = int(need / 1e6)
        if need_n and free < need:                                            # alan yetmiyorsa işi BAŞLATMA (yarım kare ve ENOSPC çöküşü yok)
            stats["disk_blocked"] = True
            print("DUR: disk yetersiz: boş %d MB < gereken %d MB" % (free / 1e6, need / 1e6), flush=True)
            return {"rendered": 0, "missing": need_n, "seconds": 0.0, "sec_per_frame": None, "engine": "puppet2d", **stats}
        w = pick_workers(workers)
        stats["workers_start"] = w; stats["mem_mb"] = available_mem_mb()
        cancel = os.path.join(out_dir, ".cancel")
        for attempt in range(4):
            todo = [j for j in jobs if not valid_png(j[1])]
            if not todo or os.path.exists(cancel):
                stats["cancelled"] = os.path.exists(cancel)
                break
            try:
                if w == 1:                                  # güvenli tek işçi yolu: ayrı süreç yok
                    _init(plan, designs)
                    for j in todo:
                        if os.path.exists(cancel):
                            stats["cancelled"] = True; break
                        done += _work(j); _beat_lock(lock)
                else:
                    ex = ProcessPoolExecutor(w, initializer=_init, initargs=(plan, designs))
                    try:
                        pending = set(); it = iter(todo); n = 0
                        while True:
                            while len(pending) < w * window_mult:       # sınırlı kuyruk: bellekte en çok w*3 görev
                                try:
                                    pending.add(ex.submit(_work, next(it)))
                                except StopIteration:
                                    break
                            if not pending:
                                break
                            fin, pending = wait(pending, timeout=frame_timeout, return_when=FIRST_COMPLETED)
                            if not fin:
                                stats["timeouts"] += 1
                                raise TimeoutError("kare zaman aşımı (%ds)" % frame_timeout)
                            for fu in fin:
                                done += fu.result(); n += 1
                            _beat_lock(lock)
                            if progress and n % 48 < len(fin):
                                print("PROGRESS kare=%d/%d  %.2f sn/kare" % (n, len(todo), (time.time() - t0) / max(1, n)), flush=True)
                            if os.path.exists(cancel):
                                stats["cancelled"] = True; break
                    finally:
                        for p_ in list(getattr(ex, "_processes", {}).values()):
                            try:
                                p_.terminate()                    # yalnız KENDİ başlattığımız işçiler
                            except Exception:
                                pass
                        ex.shutdown(wait=False, cancel_futures=True)
                break
            except (BrokenProcessPool, MemoryError, TimeoutError, RuntimeError) as e:
                stats["retries"] += 1
                print("UYARI: %s (%s); işçi sayısı %d -> %d" % (type(e).__name__, e, w, max(1, w // 2)), flush=True)
                w = max(1, w // 2)
        stats["workers_end"] = w
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass
    missing = len([j for j in jobs if not valid_png(j[1])])
    el = time.time() - t0
    return {"rendered": done, "missing": missing, "seconds": round(el, 1), "sec_per_frame": round(el / done, 3) if done else None, "engine": "puppet2d", **stats}
