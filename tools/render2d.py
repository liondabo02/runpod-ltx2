"""AHOS 2D kare çizici: plan + poz -> PNG kareleri (çok işlemcili, kaldığı yerden devam)."""
import copy, json, math, multiprocessing, os, shutil, sys, time
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
import pointing  # noqa: E402
import listener_reaction  # noqa: E402
import continuity  # noqa: E402
import pose_blend  # noqa: E402
import shot_cuts  # noqa: E402
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


LAUGH_PERIOD_S, LAUGH_SHUT_S = 2.4, 0.9        # gülen karakter gözünü dalga dalga kapatır; arada gülen gözle bakar
ACTION_LOOK_LEAD_S, ACTION_LOOK_TAIL_S = 0.5, 0.3     # nesne eylemi: hazırlıktan temas/varış sonrasına kadar gözler açık


def action_look(beat, lt):
    """Şu an izlenecek bir nesne eylemi varsa bakılacak yer: ('x', dünya_x) hedef ya da ('who', (veren, alan)); yoksa None."""
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        for e in object_state.events(tr):
            if not (e["t_start"] - ACTION_LOOK_LEAD_S <= lt <= e["t"] + ACTION_LOOK_TAIL_S):
                continue
            if e["type"] == "handoff":
                return ("who", (e["by"], e["to"]))
            if e["type"] == "pickup":
                return ("who", (e["by"],))
            k = next(k for k in tr if k["t"] == e["t"] and "at" in k)
            at = _tg(beat).get(k["at"]) if isinstance(k["at"], str) else k["at"]
            if at:
                return ("x", float(at[0]))
    return None


def eyes_state(emotion, lt, seed, blink, watching):
    """(göz kırpma, gülerken gözler açık mı). watching: nesne eylemi sürerken göz kapanmaz (ne kırpma ne gülme)."""
    if watching:
        return False, True
    if emotion != "laugh":
        return blink, False
    shut = (lt + _hash(int(seed), 11) * LAUGH_PERIOD_S) % LAUGH_PERIOD_S < LAUGH_SHUT_S
    return blink, not shut


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


SWAP_START_S = 0.10          # vuruşa elinde nesneyle giren oyuncu tercih ettiği ele bu andan itibaren geçirir (sn)
SWAP_S = 0.60                # el değiştirme süresi: nesne bir elden ötekine görünür biçimde geçer
SWAP_MIN_S = 0.35            # sonraki temas/atış yakınsa en kısa geçiş
SWAP_BEFORE_ACT_S = 0.50     # geçiş, aynı oyuncunun bu vuruştaki ilk temas/atış hazırlığından en az bu kadar önce biter


def hand_link(prev, beat):
    """Planlayıcı vuruşları sırayla bağlar: elinde nesneyle bir önceki vuruştan kesintisiz gelen oyuncu hangi elle geldi?
    beat['hand_in'] = {oyuncu: el} (yalnız bu vuruşun tercih ettiği elden farklıysa). El vuruş sınırında ışınlanmaz: o elle başlar, sonra görünür biçimde el değiştirir."""
    beat["hand_in"] = {}
    if prev is None or beat.get("transition_kind") in continuity.FREE or abs(prev["t_end"] - beat["t_start"]) > 1e-6 or prev.get("loc") != beat.get("loc"):
        return beat["hand_in"]
    pdur = prev["t_end"] - prev["t_start"]
    for cid in beat.get("cast") or []:
        if cid not in (prev.get("cast") or []):
            continue
        a, b = carry_info(prev, cid, pdur - 1e-6), carry_info(beat, cid, 0.0)
        if a and b and a["prop"] == b["prop"] and a["hand"] != pick_hand(beat, cid):
            beat["hand_in"][cid] = a["hand"]
    return beat["hand_in"]


def hand_swap(beat, cid):
    """(eski el, yeni el, başlangıç, bitiş) vuruş içi sn, ya da None."""
    old = (beat.get("hand_in") or {}).get(cid)
    new = pick_hand(beat, cid)
    if old not in ("L", "R") or old == new:
        return None
    first = beat["t_end"] - beat["t_start"]
    for ob in (beat.get("choreo") or {}).get("objects", []):
        for e in object_state.events(ob.get("track") or []):
            if cid in (e.get("by"), e.get("to")):
                first = min(first, e.get("t_start", e["t"]) - 0.45)               # atış hazırlığı / uzanma bundan önce başlamaz
    end = min(SWAP_START_S + SWAP_S, first - SWAP_BEFORE_ACT_S)
    start = max(0.0, min(SWAP_START_S, end - SWAP_MIN_S))
    end = max(end, start + SWAP_MIN_S)
    return old, new, start, end


def hand_at(beat, cid, lt):
    """O anda nesneyi tutan el: el değiştirmenin ortasına kadar eski, sonra yeni el."""
    sw = hand_swap(beat, cid)
    if sw and lt < (sw[2] + sw[3]) / 2:
        return sw[0]
    return pick_hand(beat, cid)


def swap_weight(beat, cid, lt):
    """El değiştirme sırasında iki kolun göğüs önüne uzanma ağırlığı 0..1 ve nesnenin eski elden yeni ele geçiş oranı 0..1 ya da None."""
    sw = hand_swap(beat, cid)
    if not sw or not (sw[2] <= lt <= sw[3]):
        return None
    a, b = sw[2], sw[3]; ramp = 0.3 * (b - a)
    w = pp_smooth((lt - a) / ramp) * (1.0 - pp_smooth((lt - (b - ramp)) / ramp))
    u = pp_smooth((lt - (a + ramp)) / max(1e-6, b - a - 2 * ramp))
    return w, u, sw


def _hold_pos(cid, items, designs, beat, lt, hand=None, grip=0.12):
    """Nesne TABANININ dünya konumu: çizilen elin gerçek yeri (pp.hand_offset) eksi tutuş yüksekliği (nesne elin içinde, el tutuş noktasında).
    El değiştirme sırasında nesne eski elden yeni ele sürekli geçer."""
    for cid_, d_, p_, m_, _lk, _e in items:
        if cid_ == cid:
            sw = None if hand in ("L", "R") else swap_weight(beat, cid, lt)
            if sw:
                (ox, oh), (nx, nh) = (pp.hand_offset(d_, p_, s) for s in sw[2][:2])
                u = sw[1]
                dx, h = ox + (nx - ox) * u, oh + (nh - oh) * u
            else:
                dx, h = pp.hand_offset(d_, p_, hand if hand in ("L", "R") else hand_at(beat, cid, lt))
            return p_["x"] + dx, max(0.0, h - grip), d_["height"]
    return None


def apply_hand_swap(beat, items, lt):
    """El değiştirmede iki el göğüs önünde buluşur (nesne eski elden yeniye geçerken ikisi de nesnede)."""
    for cid, des, p, *_ in items:
        sw = swap_weight(beat, cid, lt)
        if not sw or pp.view_of(p) == "side":
            continue
        w = sw[0]
        ln = des["height"] * 0.27
        sh = {s: pp.shoulder_offset(des, p, s) for s in "LR"}
        mx = (sh["L"][0] + sh["R"][0]) / 2
        mh = (sh["L"][1] + sh["R"][1]) / 2 - 0.65 * ln
        split = pp.HAND_R_K * des["height"]
        old, new = sw[2][0], sw[2][1]
        for side in "LR":
            up = (1.0 - sw[1]) if side == old else sw[1]           # nesneyi o an daha çok taşıyan el üstte (iki el aynı noktaya binmez)
            pp.arm_blend(des, p, side, mx, mh + split * (2.0 * up - 1.0), w, inward=True)


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


def _mouth(beat, at):
    """Adlı hedef bir kabın ağzıysa (ağız_x, ağız_y), değilse None."""
    g = setpieces2d.mouth_of(at)
    return (float(_tg(beat)[at][0]), g["rim"]) if g and at in _tg(beat) else None


SINK_WALL_PAD = 0.04          # alçaktan atışta nesne kabın yan duvarından en az bu kadar açıkta yükselir (m)


def _objects_now(beat, items, lt, items_at=None):
    """[(ob, x, y, state, owner, hand)] — her nesne için konum (tutuş noktası dahil) ve çizim sahibi.
    items_at(t) -> o anın oyuncu pozları: verilirse kap içine atışta bırakma noktası bırakma ANININ elinden alınır."""
    out = []
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        sc = ob.get("scale", 0.55); grip = object_state.grip_of(ob["prop"], sc)
        def hold(holder, t_, hand=None, _g=grip):
            its = items_at(t_) if items_at is not None and abs(t_ - lt) > 1e-9 else items
            h = _hold_pos(holder, its, None, beat, t_, hand, _g)
            return (h[0], h[1]) if h else (0.0, 0.0)
        def target(at):
            at = _tg(beat)[at] if isinstance(at, str) else at
            return (at[0], at[1])
        def sink(at, _p=ob["prop"], _s=sc):
            m = _mouth(beat, at)
            if not m:
                return None
            below, above, w_ = props2d.extent(_p, _s)
            return (m[0], m[1], below + above, below, setpieces2d.mouth_of(at)["half"] + w_ + SINK_WALL_PAD)
        x, y, st = object_state.position(tr, lt, hold, target, sink_fn=sink)
        if x is None:
            continue                                            # imha (açık hide olayı, yalnız tanımlı hedefte): kutunun ağzında asılı kalmaz
        own = object_owner(st)
        into = _entry_target(beat, tr, st)
        if into and lt > into[0]:
            own = None                                          # bırakıldı: elin değil, serbest nesne (parmak çizilmez)
        out.append((ob, x, y, st, own, hand_at(beat, own, lt) if own else None))
    return out


def _entry_target(beat, track, st):
    """Nesne şu an bir kabın ağzına gidiyorsa (bırakma anı, (ağız_x, ağız_y)); değilse None."""
    if st["state"] != "put":
        return None
    for a, b in zip(track, track[1:]):
        if "holder" in a and b.get("hide") and a["holder"] == st["holder"]:
            m = _mouth(beat, b.get("at"))
            return (a["t"], m) if m else None
    return None


def _released(beat, track, st, lt):
    """Nesne kabın ağzına doğru elden AYRILDI mı? İz anahtarı 'put' dese de uçuş boyunca kimse tutmuyor."""
    into = _entry_target(beat, track, st)
    return bool(into) and lt > into[0]


def _reach_windows(beat, track):
    """Otomatik uzanma pencereleri. Kaba atış için üretilmez: hazırlık, savurma ve takibi apply_throw_swing verir. Genel 'uzanma' pozu
    nesnenin kaba vardığı ana bağlıydı; boş el nesne uçarken ikinci kez uzanıyordu."""
    thrown = {b["t"] for a, b in zip(track, track[1:]) if "holder" in a and b.get("hide") and _mouth(beat, b.get("at"))}
    return [w for w in object_state.reach_windows(track) if not (w["kind"] == "dispose" and w["t1"] in thrown)]


def _clip_above(cv, cam, world_y, draw):
    """draw'u uygula ama world_y çizgisinin ALTINDA kalan pikselleri geri al (nesne kabın gövdesi arkasında)."""
    cut = int(round(cam.y(world_y) * cv.ss))
    cut = max(0, min(cv.img.size[1], cut))
    if cut >= cv.img.size[1]:
        draw(cv, cam); return
    box = (0, cut, cv.img.size[0], cv.img.size[1])
    keep = cv.img.crop(box)
    draw(cv, cam)
    cv.img.paste(keep, box)


def _draw_objects(cv, cam, beat, items, designs, lt, owner="__free__", emit=None, items_at=None):
    """Nesneleri çizer. owner='__free__': serbest nesneler (yerde, uçuşta); owner=cid: o karakterin elindekiler (karakterden HEMEN sonra, parmaklar önde)."""
    by = {i[0]: i for i in items}
    for ob, x, y, st, own, hand in _objects_now(beat, items, lt, items_at):
        late = st["state"] == "transfer"                        # el değiştirirken nesne iki karakterin de ÖNÜNDE (alıcı karakter vericiyi örtüp nesneyi gizlemesin)
        slot = "__late__" if late else ("__free__" if own is None else own)
        if slot != owner:
            continue
        full = lambda c, cm, o_=ob, x_=x, y_=y: props2d.draw(c, cm, o_["prop"], x_, y_, 0.0, 0, scale=o_.get("scale", 0.55))
        body = full
        into = _entry_target(beat, ob.get("track") or [], st)
        if into:
            mx_, rim_ = into[1]
            half_ = max(setpieces2d.MOUTHS[k]["half"] for k in setpieces2d.MOUTHS)
            if abs(x - mx_) <= half_:               # ağzın üstünden içeri iniyor: çizgi altı görünmez (ağız dışında kırpma YOK: ıska gizlenmez)
                def body(c, cm, f_=full, r_=rim_):
                    _clip_above(c, cm, r_, f_)
                body.full = full
        body(cv, cam)
        if emit is not None:
            emit("object", ob.get("id") or ob.get("prop", "obj"), body, (x, y))
        grippers = [(own, hand)] if own is not None else []
        sw_ = swap_weight(beat, own, lt) if own is not None else None
        if sw_ and sw_[0] > 0.5:                                # kendi içinde el değiştirme: iki elin parmakları da nesnede
            grippers = [(own, s_) for s_ in sw_[2][:2]]
        if st["state"] == "transfer":                           # el değiştirmede İKİ el de nesnede: alıcı elin parmakları da önde çizilir (verenin saçı/gövdesi alıcı eli örtmez)
            grippers = [(c, hand if c == own else pick_hand(beat, c)) for c in (st["holder"], st["to"])]
        for g_cid, g_hand in grippers:                          # parmaklar nesnenin ÖNÜNDE: avuç nesneyi kavrar
            if g_cid not in by:
                continue
            _c, d_, p_, _m, _l, _e = by[g_cid]
            grip_ = lambda c, cm, d2=d_, p2=p_, h2=g_hand: pp.draw_grip(c, d2, p2, h2, cm.x(p2["x"]), cm.y(0.0), cm.s)
            grip_(cv, cam)
            if emit is not None:
                emit("grip", g_cid, grip_)


def object_effects(beat, cid, lt):
    """Nesne olaylarından oyuncu etkisi: (uzanma yerel zamanı, uzanma süresi) veya None; ve taşınan ağırlık (kg-benzeri) -> poz farkı.
    Alma/verme/bırakma'da karakter temastan ÖNCE uzanır (hazırlık), temas anında kol en uzakta (tepe)."""
    reach = None; weight = 0.0
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        for w in _reach_windows(beat, tr):
            if w["actor"] == cid and w["t0"] <= lt <= w["t1"] + (w["t1"] - w["t0"]):
                reach = (lt - w["t0"], 2.0 * max(0.3, w["t1"] - w["t0"]))
        st = object_state.state_at(tr, lt)
        if _released(beat, tr, st, lt):
            continue
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
                pp.arm_blend(des, p, side, mx - xs_, mh, w)


SWING_RELEASE_LEAD_S = 0.15


def apply_throw_swing(beat, items, lt):
    """Atış/bırakma kolu: bırakmadan önce geri salınım, bırakma anında hedefe doğru ileri savurma (kol nesneyi gerçekten fırlatır), sonra gevşeme."""
    by = {i[0]: i for i in items}
    for ob in (beat.get("choreo") or {}).get("objects", []):
        for e in object_state.events(ob.get("track") or []):
            if e["type"] not in ("dispose", "drop") or e["by"] not in by:
                continue
            ts = e["t_start"]; tgt = None; lead = 0.0
            for k in ob["track"]:
                if isinstance(k.get("at"), str) and k["t"] == e["t"]:
                    tgt = _tg(beat).get(k["at"])
                    if k.get("hide") and _mouth(beat, k["at"]):
                        lead = SWING_RELEASE_LEAD_S       # kaba atış: savurma BIRAKMA anında tepeye varır (el, bıraktığı nesneyi geçip önüne atlamaz)
            ts -= lead
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
            pp.arm_blend(des, p, side, tx, th, w)


def pp_smooth(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


CHEST_HOLD_DROP_K = 0.20      # göğüs tutuşunda el omzun kol boyunun bu katı kadar altındadır
CHEST_HOLD_FLOOR_K = 0.90     # yüzden kaçınmak için el en çok bu kadar iner (daha aşağısı kalçada sallanan nesne okunur)


def chest_hold_height(des, pose, hand_dx, shoulder_h, prop, scale):
    """Göğüste tutan elin yüksekliği: göğüs hizası; nesnenin ÇİZİLEN üstü yüze binecekse el o kadar iner (yüzü kapatan ya da ağza
    dayanan nesne 'su içiyor' okunur). Uzun nesnede alt sınır geçerlidir (o durum bu kuralla çözülmez)."""
    arm = des["height"] * 0.27
    below, above, half = props2d.extent(prop, scale)
    grip = object_state.grip_of(prop, scale)
    h = shoulder_h - CHEST_HOLD_DROP_K * arm
    lim = pp.below_face(des, pose, hand_dx - half, hand_dx + half)
    if lim is not None:
        h = min(h, lim - max(0.0, above - grip))
    return max(shoulder_h - CHEST_HOLD_FLOOR_K * arm, h)


def carry_info(beat, cid, lt):
    """Karakter şu an bir nesne taşıyorsa {'prop','weight','style','hand','reach'} (ağırlık merkezi: yük gövdeden ne kadar önde), yoksa None."""
    best = None
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        st = object_state.state_at(tr, lt)
        if _released(beat, tr, st, lt):                      # kaba atılan nesne bırakıldı: artık taşınmıyor, boş kol tutma pozuna dönmez
            continue
        mine = (st["state"] in ("held", "put") and st["holder"] == cid) or (st["state"] == "transfer" and cid in (st["holder"], st["to"]))
        if not mine:
            continue
        w = object_state.weight_of(ob["prop"])
        if best is None or w > best["weight"]:
            sty = object_state.carry_style(ob["prop"])
            best = {"prop": ob["prop"], "scale": ob.get("scale", 0.55), "weight": w, "style": sty, "hand": hand_at(beat, cid, lt),
                    "reach": 0.25 if sty == "two_hand_front" else 0.15}
    return best


HEAD_TOP_K = 1.08          # başın tepesi (saç/başlık payıyla) / boy
HEAD_MARGIN_PX = 12.0      # geniş/orta planda en uzun başın üstünde kalan en az pay
FEET_MAX_PX = 690.0        # kamera yükselirken ayak zemini bundan aşağı inemez; inecekse kadraj açılır


def head_safe_framing(cy, zoom, tallest, base_ppm):
    """Geniş/orta plan için (cy, zoom): en uzun oyuncunun başı üstten kesilmez. Yeten kadraj aynen kalır."""
    if tallest <= 0:
        return cy, zoom
    top = tallest * HEAD_TOP_K
    zoom = min(zoom, (FEET_MAX_PX - HEAD_MARGIN_PX) / (base_ppm * top))
    return max(cy, top - (360.0 - HEAD_MARGIN_PX) / (base_ppm * zoom)), zoom


def head_chin_k(design):
    """Çenenin boya oranı (baş kutusunun alt sınırı): küçük oyuncuda baş büyüktür."""
    return 0.50 if design["height"] < 1.3 else 0.70


def _head_cropped(cam, x, H):
    """Başın/saçın/omzun ekran sınırında KISMEN kesilip kesilmediği (tamamen içerde/tamamen dışarıda sorun değil).
    Çocukta baş büyük (çene ~0.50H), yetişkinde çene ~0.70H; alt kenarda ön plan çimi (y>640) yüzü örter."""
    hw = 0.30 * H * cam.s; cx = cam.x(x); top = cam.y(H * 1.02); bot = cam.y(H * (0.50 if H < 1.3 else 0.70))
    inside_x = (cx - hw >= 0) and (cx + hw <= 1280)
    outside_x = (cx + hw <= 0) or (cx - hw >= 1280)
    inside_y = (top >= 0) and (bot <= 640)
    outside_y = bot <= 0 or top >= 720
    return not ((inside_x and inside_y) or outside_x or outside_y)

CROP_WAIST_PAD_K = 0.03    # kasıtlı üst beden kesmesi kalçanın bu kadar (boy katı) üstünden yapılır
CROP_TOP_PX = 90.0         # üst beden planında itme (push-in) öncesi baş tepesinin üstünde kalan pay
CROP_ZOOM_MAX = 3.6
CROP_PUSH_PH, CROP_PUSH_E = 0.05, 0.04      # üst beden planında yavaş yaklaşma ve vurgu itmesi (alt kenar sabit kalır)
CROP_OBJ_PAD_PX = 70.0     # tutulan konu nesnesinin alt kenarı ekran altından en az bu kadar yukarıda (ön plan çimi nesneyi örtmesin)


def hip_height(design):
    """Ayakta kalça yüksekliği (m): alt kadraj kenarı bunun altından geçerse bacak ortasından kesilmiş olur."""
    return design["height"] * pp.LEG_K[design["class"]]


def frame_bottom(cam):
    """Ekranın alt kenarının dünya yüksekliği (m)."""
    return cam.cy - (pp.H / 2) / cam.s


CLOSE_PRESETS = ("close", "xclose")
CHOICE_STEP_S = 1.0 / 24                          # yakın çekimin sınırları bu aralıkla bulunur (yalnız kurgu kararı; poz hesabı yok)


def speaker_at(beat, t):
    """t anında replik söyleyen (yoksa None)."""
    return next((ln["char"] for ln in reversed(beat.get("lines") or []) if ln["start"] <= t < ln["end"]), None)


def layered_choice(beat, t):
    """Katmanların (kurgu listesi, konuşan, tepki, şaşırma, gösterme, temas) t anında tek tek istediği plan: (plan türü, odak, yaklaşma oranı).
    Bu HAM istektir; ekrandaki plan camera_choice'tur."""
    lt = t - beat["t_start"]
    speaker, focus = speaker_at(beat, t), beat.get("focus")
    reaction = reaction_target(beat, t)               # tepki planı: replik bitince / uzun replikin ortasında dinleyene kesilir
    if reaction:
        focus = reaction
    elif speaker and speaker in beat["cast"]:       # yakın planda kamera hep o an konuşana bakar (yüz + omuz kadrajda)
        focus = speaker
    preset, ph, _shot = shot_cuts.at(beat, lt)   # kurgu listesi: yalnız gerçek kesmeler; yavaş yaklaşma çekim boyunca bir kez ilerler
    if lt < 1.4 and any(m_["kind"] == "surprise" for m_ in (beat.get("motion") or {}).values()):
        preset = "xclose"                               # şaşırma anında aşırı yakın plan (yüz dolsun)
    if reaction:
        preset = "close"                                # tepki planı her zaman yakın plan
    if pointing.window_at(beat, lt):
        preset = "point"                                # gösterme jesti: gösteren ve hedef birlikte (tepki/yakın plan kesmesi yapılmaz)
    if any(w[0] <= lt <= w[1] for w in action_staging.hold_windows(beat)):
        preset = "action"                               # temas penceresi: sabit aksiyon kadrajı
    return preset, focus, ph


def _layer_key(beat, lt):
    """Ham isteğin plan kimliği: (tür, yakın planda odak, sabit kadrajda pencere sırası)."""
    preset, focus, _ph = layered_choice(beat, beat["t_start"] + lt)
    wins = action_staging.hold_windows(beat) if preset == "action" else pointing.shot_windows(beat) if preset == "point" else ()
    win = next((i for i, w in enumerate(wins) if w[0] <= lt <= w[1]), None)
    return preset, focus if preset in CLOSE_PRESETS else None, None if win is None else (beat["t_start"], win)


def _layer_segments(beat):
    """Vuruşun ham isteğinin plan dilimleri (mutlak sn); sınırlar ikiye bölerek bulunur. parts: o planın gerçekten istendiği aralıklar."""
    t0, dur = beat["t_start"], beat["t_end"] - beat["t_start"]
    last_lt = max(0.0, dur - 1e-6)
    out, lo, key = [], 0.0, _layer_key(beat, 0.0)
    first = 0.0
    n = max(1, int(math.ceil(dur / CHOICE_STEP_S - 1e-6)))
    for k in range(1, n + 1):
        hi = min(last_lt, k * CHOICE_STEP_S)
        while True:
            now = _layer_key(beat, hi)
            if now == key:
                break
            a, b = lo, hi
            while b - a > 1e-7:
                m = (a + b) / 2
                a, b = (m, b) if _layer_key(beat, m) == key else (a, m)
            out.append((key, first, b, a))
            first, lo, key = b, b, _layer_key(beat, b)
        lo = hi
    out.append((key, first, dur, last_lt))
    return [{"key": k_, "a": t0 + a, "b": t0 + b, "bounds": None if k_[2] is None else (t0, beat["t_end"]),
             "parts": [(beat, a, last)]} for k_, a, b, last in out]


_CUT_CACHE = {}


def _run_of(plan, beat):
    """beat'in içinde olduğu kesintisiz sahne parçası (aynı mekân ve kadro, sürekli geçiş); pencere dışı komşular plan['context']'tedir."""
    order = _timeline(plan)
    i = next((n for n, b_ in enumerate(order) if b_ is beat), None)
    if i is None:
        return [beat]
    a = b = i
    while a > 0 and shot_cuts.continues(order[a - 1], order[a]):
        a -= 1
    while b + 1 < len(order) and shot_cuts.continues(order[b], order[b + 1]):
        b += 1
    return order[a:b + 1]


def final_cut(plan, beat):
    """Kesintisiz sahne parçasının SON plan dizisi (bütün katmanlar birleştikten sonra, anlık kırıntılar eritilmiş). Plan verisi değişince yeniden hesaplanır."""
    run = _run_of(plan, beat)
    code = (layered_choice, reaction_target, shot_cuts.at, shot_cuts.dissolve_crumbs, action_staging.hold_windows, pointing.shot_windows,
            pointing.window_at, listener_reaction.MIN_SHOT_S)
    key = tuple(id(b_) for b_ in run)
    hit = _CUT_CACHE.get(key)
    if hit is None or hit[0] != code or hit[1] != run:
        segs = [s_ for b_ in run for s_ in _layer_segments(b_)]
        if len(_CUT_CACHE) >= 256:
            _CUT_CACHE.clear()
        hit = _CUT_CACHE[key] = (code, copy.deepcopy(run), shot_cuts.dissolve_crumbs(segs, listener_reaction.MIN_SHOT_S))
    return hit[2]


def chosen_shot(plan, beat, t):
    """t anının ekrandaki planı: {'preset','focus','ph','window','src_lt'}. src_lt: bu planın verisinin okunacağı vuruş içi an
    (plan komşu kırıntıyı üstlendiyse kendi istendiği en yakın an; yoksa t'nin kendisi)."""
    segs = final_cut(plan, beat)
    seg = next((s_ for s_ in reversed(segs) if s_["a"] <= t + 1e-6), segs[0])
    lt = t - beat["t_start"]
    preset, focus, window = seg["key"]
    raw = layered_choice(beat, t)
    if _layer_key(beat, lt) == seg["key"]:
        return {"preset": preset, "focus": raw[1], "ph": raw[2], "window": window, "src_lt": lt}

    def gap(part):
        b_, a, b = part
        return max(b_["t_start"] + a - t, t - (b_["t_start"] + b), 0.0)
    src, a, b = min(seg["parts"], key=gap)
    src_lt = max(a, min(b, t - src["t_start"]))
    _p, src_focus, ph = layered_choice(src, src["t_start"] + src_lt)
    return {"preset": preset, "focus": focus or (src_focus if src_focus in beat["cast"] else raw[1]), "ph": ph, "window": window,
            "src_lt": src_lt if window is not None else lt}


def camera_choice(plan, beat, t):
    """t anının kurgu kararı (saf veri; çizim ve poz hesabı yok): (plan türü, odak, yaklaşma oranı). frame() ve kadraj ihtiyacı aynı kararı kullanır."""
    c = chosen_shot(plan, beat, t)
    return c["preset"], c["focus"], c["ph"]


def _choice_spans(plan, beat):
    """Vuruşun ekrandaki plan aralıkları: [((tür, odak), başlangıç, bitiş)] (vuruş içi sn), son plan dizisinden."""
    t0, dur, out = beat["t_start"], beat["t_end"] - beat["t_start"], []
    for s_ in final_cut(plan, beat):
        a, b = max(0.0, s_["a"] - t0), min(dur, s_["b"] - t0)
        if b - a > 1e-6:
            out.append((s_["key"][:2], a, b))
    return out


def close_run(plan, beat, lt, key):
    """lt anını içeren, aynı yüzdeki kesintisiz yakın çekim: [(vuruş, a, b)] (vuruş içi sn).
    Çekim sürekli geçişte vuruş sınırını aşar; planın üretim penceresi dışındaki komşuları plan['context'] verisindedir."""
    own = _choice_spans(plan, beat)
    hit = [r for r in own if r[0] == key and r[1] - CHOICE_STEP_S <= lt <= r[2] + CHOICE_STEP_S]
    if not hit:
        return [(beat, lt, lt)]
    span = min(hit, key=lambda r: max(r[1] - lt, lt - r[2], 0.0))
    run = [(beat, span[1], span[2])]
    order = sorted(list(plan.get("context") or []) + [b_ for b_ in plan["beats"]], key=lambda b_: b_["t_start"])
    i = next((n for n, b_ in enumerate(order) if b_ is beat), None)
    if i is None:
        return run
    for step in (-1, 1):
        cur, spans, edge, j = beat, own, span, i + step
        while 0 <= j < len(order):
            dur = cur["t_end"] - cur["t_start"]
            if edge != (spans[0] if step < 0 else spans[-1]) or (edge[1] > 1e-6 if step < 0 else edge[2] < dur - 1e-6):
                break
            nxt = order[j]
            if not (shot_cuts.continues(nxt, cur) if step < 0 else shot_cuts.continues(cur, nxt)):
                break
            spans = _choice_spans(plan, nxt)
            edge = spans[-1] if step < 0 else spans[0]
            if edge[0] != key:
                break
            run.insert(0, (nxt, edge[1], edge[2])) if step < 0 else run.append((nxt, edge[1], edge[2]))
            cur, j = nxt, j + step
    return run


def run_phase(run, beat, lt):
    """Yakın çekimin yavaş yaklaşma oranı 0..1: çekim boyunca BİR KEZ ilerler. Alttaki kurgu listesinin sınırı (tepki planı onu örterken)
    ya da vuruş sınırı yaklaşmayı başa alıp kadrajı tek karede oynatamaz."""
    total = sum(b - a for _b, a, b in run)
    done = 0.0
    for b_, a, b in run:
        if b_ is beat and a - CHOICE_STEP_S <= lt <= b + CHOICE_STEP_S:
            done += max(0.0, min(b, lt) - a)
            break
        done += b - a
    return max(0.0, min(1.0, done / max(total, 0.1)))


def shot_needs(plan, designs, cid, run):
    """cid yakın plandayken kadrajın bilmesi gerekenler, yalnız BU yakın çekim boyunca (4 fps + son an), çizimin gerçek pozlarından:
    'held' elinde tuttuğu nesnelerin en alçak alt kenarı (m; tutmuyorsa None), 'rise' en yüksek zıplama (m), 'sink' en derin oturma (m).
    Çekim boyunca tek değerdir (vuruş sınırını aşan çekimde de): kadraj kare kare ya da sınırda sıçramaz; çekimde olmayan tutuş/oturuş kadrajı açmaz."""
    out = {"held": None, "rise": 0.0, "sink": 0.0}
    for beat, a, b in run:
        view, memo = dict(plan, beats=[beat]), {}

        def at(t_, _beat=beat, _view=view, _memo=memo):
            if t_ not in _memo:
                _memo[t_] = poses_at(_view, designs, _beat["t_start"] + t_) or []
            return _memo[t_]
        end = max(a, min(b, beat["t_end"] - beat["t_start"]) - 1e-3)
        times = [a + i / 4.0 for i in range(int(math.ceil((end - a) * 4 - 1e-9)))] + [end]
        for lt in times:
            for it in at(lt):
                if it[0] == cid:
                    z = float(it[2].get("z", 0.0))
                    out["rise"], out["sink"] = max(out["rise"], z), max(out["sink"], -z)
            for ob, _x, y, _st, own, _h in _objects_now(beat, at(lt), lt, at):
                if own == cid:
                    low = y - props2d.extent(ob.get("prop", ""), ob.get("scale", 0.55))[0]
                    out["held"] = low if out["held"] is None else min(out["held"], low)
    return out


SIT_FULL_K = 0.05          # bundan (boy katı) derin oturan oyuncu üst bedenden kesilmez: tam boy gösterilir


def crop_safe_framing(cy, zoom, design, base_ppm, needs=None, ph=0.0, E=0.0):
    """Yakın plan için (cy, zoom, kip). Alt kenar bacakların ortasından ya da konu nesnesinden geçmez:
    'full'  ayak zemini kadrajda (yetiyorsa eski kadraj aynen kalır),
    'upper' KASITLI üst beden kesmesi: alt kenar kalçanın üstünde, tutulan nesne tamamen içeride.
    Eski kadraj bacaktan kesiyorsa üst bedene yaklaşılır; oyuncu oturuyorsa ya da tutulan nesne kalçadan aşağıdaysa tam boya açılır.
    needs: shot_needs çıktısı."""
    needs = needs or {}
    held = needs.get("held")
    Hh = design["height"]; top = Hh * HEAD_TOP_K + needs.get("rise", 0.0); hip = hip_height(design)
    sits = needs.get("sink", 0.0) > SIT_FULL_K * Hh
    s = base_ppm * zoom
    if pp.H / 2 + cy * s <= FEET_MAX_PX:
        return cy, zoom, "full"
    if not sits:
        cut_now = cy - (pp.H / 2) / s
        if cut_now >= hip and pp.H / 2 - (top - cy) * s >= HEAD_MARGIN_PX and (held is None or cut_now <= held - CROP_OBJ_PAD_PX / s):
            return cy, zoom, "upper"
        k = CROP_OBJ_PAD_PX / (pp.H - CROP_TOP_PX)      # üst beden kadrajında nesne payı kadraj ölçeğiyle birlikte çözülür
        low = None if held is None else (held - k * top) / (1.0 - k)
        if low is None or low >= hip:
            cut = hip + Hh * CROP_WAIST_PAD_K
            if low is not None:
                cut = min(cut, low)
            z = min(CROP_ZOOM_MAX, (pp.H - CROP_TOP_PX) / (top - cut) / base_ppm) * (1.0 + CROP_PUSH_PH * ph) * (1.0 + CROP_PUSH_E * E)
            return cut + (pp.H / 2) / (base_ppm * z), z, "upper"
    zoom = min(zoom, (FEET_MAX_PX - HEAD_MARGIN_PX) / (base_ppm * top))
    s = base_ppm * zoom
    return max(top - (pp.H / 2 - HEAD_MARGIN_PX) / s, min(cy, (FEET_MAX_PX - pp.H / 2) / s)), zoom, "full"


FOLLOW_CALM_MPS, FOLLOW_FULL_MPS = 0.03, 0.18      # odaktaki oyuncu bundan yavaşsa vurgu itmesi tam; bundan hızlıysa yok (arada sürekli)


def follow_steadiness(beat, designs, cid, lt):
    """1: kamera duran oyuncuda; 0: yürüyen oyuncuyu izliyor. Yürüyüşün başı ve sonunda sürekli geçer."""
    m = (beat.get("motion") or {}).get(cid)
    if not m or cid not in designs:
        return 1.0
    dur, H = beat["t_end"] - beat["t_start"], designs[cid]["height"]
    v = max(abs(sm.motion_x(m, max(0.0, min(dur, lt + d)), dur, H) - sm.motion_x(m, max(0.0, min(dur, lt + d - 0.5)), dur, H)) / 0.5
            for d in (0.0, 0.5))
    return max(0.0, min(1.0, (FOLLOW_FULL_MPS - v) / (FOLLOW_FULL_MPS - FOLLOW_CALM_MPS)))


def reaction_target(beat, t):
    """Tepki planında kamera kimde olmalı? (karar: listener_reaction; dinleyen yoksa None). Aksiyon kadrajı süren aralıklar tepki planına sayılmaz."""
    return listener_reaction.target(beat, t, action_blocks(beat))


def action_blocks(beat):
    """Sabit aksiyon ve gösterme kadrajının sürdüğü aralıklar (mutlak sn): bu aralıklarda tepki planına kesilmez."""
    if "t_start" not in beat or "t_end" not in beat:
        return []
    return [(beat["t_start"] + w[0], beat["t_start"] + w[1]) for w in action_staging.hold_windows(beat) + pointing.shot_windows(beat)]


def _speech(beat, t):
    """O anda konuşan ve vurgu şiddeti: (konuşan | None, 0..1)."""
    ln = next((ln for ln in beat["lines"] if ln["start"] <= t < ln["end"]), None)
    speaker = next((ln_["char"] for ln_ in reversed(beat["lines"]) if ln_["start"] <= t < ln_["end"]), None)
    if speaker is None:
        return None, 0.0
    cues = next((ln_["cues"] for ln_ in beat["lines"] if ln_["char"] == speaker and ln_["start"] <= t < ln_["end"]), [])
    start = next((ln_["start"] for ln_ in beat["lines"] if ln_["char"] == speaker and ln_["start"] <= t < ln_["end"]), 0)
    return speaker, emphasis(cues, t - start)


def actor_state(beat, designs, cid, lt, px):
    """Oyuncunun o andaki AYRIK durumu (tek kaynak: poz hesabı ve geçiş imzası aynı kararı okur).
    Dönüş: hareket sözlüğü, eylem türü, yerel zaman ve süreler, yönetmen tepkisi sürüyor mu, taşıma bilgisi, 'duran taşıyor' mu."""
    m, dur = beat["motion"][cid], beat["t_end"] - beat["t_start"]
    rc = ((beat.get("choreo") or {}).get("react") or {}).get(cid)           # yönetmen tepkisi: belirli andan sonra (ör. şaşırma)
    m, seg_t, seg_d = sm.segment(m, lt, dur)             # yaklaşma yürüyüşü varsa o parça; yoksa eylemin kendisi
    lte, kind_e = seg_t, m["kind"]
    reacting = bool(rc) and lt >= float(rc["t"])
    if reacting:
        lte, kind_e = lt - float(rc["t"]), rc["kind"]
        m = dict(m); m["kind"] = kind_e; m["x0"] = m["x1"] = _x_at(px, cid, m); seg_d = dur
    reach_w, _carry_w = object_effects(beat, cid, lt)
    dur_e = seg_d
    if reach_w and kind_e in ("idle", "look") and not rc:      # nesne teması yaklaşıyor ve karakter boşta: uzanma hazırlığı otomatik
        lte, dur_e, kind_e = reach_w[0], reach_w[1], "reach"
        m = dict(m); m["kind"] = "reach"; m["x0"] = m["x1"] = _x_at(px, cid, m)
    ci = carry_info(beat, cid, lt)
    stationary = (kind_e not in ("walk", "carry", "run")) or (kind_e == "walk" and (abs(m["x1"] - m["x0"]) < 0.02 or lt >= 0.9 * seg_d))      # yürüyüp varmış karakter de duran sayılır
    return {"m": m, "kind": kind_e, "lte": lte, "dur": dur_e, "seg_d": seg_d, "reacting": reacting, "carry": ci, "stationary": stationary}


def _history(plan, cid, beat, t):
    """t anı için bu oyuncunun kesintisiz geçmişindeki vuruş: bu vuruş ya da aynı mekânda hemen önceki (zaman atlaması yoksa)."""
    while beat is not None and t < beat["t_start"] - 1e-9:
        prev = None
        if beat.get("transition_kind") not in continuity.FREE:
            prev = next((b for b in plan["beats"] if abs(b["t_end"] - beat["t_start"]) < 1e-6 and b.get("loc") == beat.get("loc")
                         and cid in b["cast"]), None)
        beat = prev
    return beat if beat is not None and cid in beat["cast"] else None


def _positions(beat, designs, lt):
    dur = beat["t_end"] - beat["t_start"]
    return {c: sm.motion_x(beat["motion"][c], lt, dur, designs[c]["height"]) for c in beat["cast"]}


def pose_signature(plan, designs, beat, cid, t):
    """Pozu değiştiren ayrık kararların imzası; bu değişince beden yeni poza geçişle varır (pose_blend)."""
    b = _history(plan, cid, beat, t)
    if b is None:
        return None
    lt = t - b["t_start"]
    px = _positions(b, designs, lt)
    st = actor_state(b, designs, cid, lt, px)
    ci = st["carry"]
    speaker = _speech(b, t)[0]
    hear = None if speaker == cid else listener_reaction.performance(b, cid, t)
    gz = ((b.get("choreo") or {}).get("gaze") or {}).get(cid)
    side = px[gz] > px[cid] if gz in px and gz != cid else None              # bakılan oyuncu öbür yana geçerse baş yön değiştirir
    return (b["t_start"], st["kind"], st["reacting"], speaker, hear and hear["speaker"], side,
            None if not ci else (ci["hand"], ci["style"], ci["prop"], st["stationary"]))


def actor_pose(plan, designs, beat, cid, t, px):
    """Oyuncunun t anındaki taban pozu (temas katmanlarından önce), durum değişimlerinde geçişli: (poz, hareket, bakış, vurgu)."""
    now = _base_pose(plan, designs, beat, cid, t, px)

    def raw(t_):
        if abs(t_ - t) < 1e-12:
            return now[0]
        b = _history(plan, cid, beat, t_)
        return _base_pose(plan, designs, b, cid, t_, _positions(b, designs, t_ - b["t_start"]))[0]
    p = pose_blend.apply(raw, lambda t_: pose_signature(plan, designs, beat, cid, t_), t, designs[cid]["height"])
    return (p,) + now[1:]


def _base_pose(plan, designs, beat, cid, t, px):
    """Tek anın geçişsiz taban pozu: (poz, hareket, bakış, vurgu)."""
    lt = t - beat["t_start"]
    speaker, E = _speech(beat, t)
    d = designs[cid]
    Hm = d["height"]
    st_ = actor_state(beat, designs, cid, lt, px)
    m, kind_e, lte, dur_e, seg_d = (st_[k] for k in ("m", "kind", "lte", "dur", "seg_d"))
    args = (kind_e, 0, dur_e, m["seed"], m["x0"], m["x1"], Hm, Hm * 0.45)
    spk = (cid == speaker)
    p = sm.pose_at(args[0], lte, *args[2:], speaking=spk)
    # takip (follow-through): kollar gövdeden, kafa da biraz geriden gelir
    pa = sm.pose_at(args[0], max(0.0, lte - 0.11), *args[2:], speaking=spk)
    ph_ = sm.pose_at(args[0], max(0.0, lte - 0.05), *args[2:], speaking=spk)
    p["aL"], p["aR"], p["head"] = list(pa["aL"]), list(pa["aR"]), list(ph_["head"])
    ci = st_["carry"]
    if ci:                                                     # taşıma: ağırlık + taşıma biçimi (yük önde/yanda/omuzda) -> denge, kol pozu
        adj = object_state.carry_adjust(ci["weight"], ci["style"], ci["reach"])
        p["lean"] += adj["lean"]; p["sq"] = p.get("sq", 1.0) + adj["sq"]; p["head"][0] += adj["head_nod"]
        if kind_e != "reach":                                  # tepki (şaşırma/gülme) sırasında da tutan kol nesneyi taşımaya devam eder
            ha = "aL" if ci["hand"] == "L" else "aR"; sg_ = 1 if ci["hand"] == "L" else -1
            for s_ in (("L", "R") if adj["arms"] == "both_front" else (ci["hand"],)):
                p.pop("sw" + s_, None)                          # taşıyan kol yürüyüş salınımına katılmaz
            if adj["arms"] == "both_front":
                for a_ in ("aL", "aR"):
                    p[a_][0] = -0.95
                p["aL"][1] = 0.30; p["aR"][1] = -0.30
            elif adj["arms"] == "one_up":
                p[ha][0] = -0.40; p[ha][1] = sg_ * 1.6
            else:
                p[ha][0] = -0.35; p[ha][1] = sg_ * 0.25
                p["head"][1] += -sg_ * adj["side_tilt"]
                if st_["stationary"] and ci["weight"] < 1.5 and ci["style"] != "two_hand_front":
                    # duran kişi hafif nesneyi kalça hizasında sallamaz: dirseği bükük, nesne göğüs hizasında önde tutar (boy ve kola göre; çocuk yüzüyle aynı hizaya düşmez)
                    gz_ = ((beat.get("choreo") or {}).get("gaze") or {}).get(cid)
                    dn = (1.0 if px[gz_] > px[cid] else -1.0) if gz_ in px and gz_ != cid else (1.0 if ci["hand"] == "R" else -1.0)
                    ln_ = Hm * 0.27; shx_, shh_ = pp.shoulder_offset(d, p, ci["hand"])
                    tx_ = shx_ + dn * 0.12 * ln_
                    pp.arm_toward(d, p, ci["hand"], tx_, chest_hold_height(d, p, tx_, shh_, ci["prop"], ci["scale"]))
    look = 0.0
    gz = ((beat.get("choreo") or {}).get("gaze") or {}).get(cid)       # yönetmen bakışı: konuşulan kişiye/nesneye
    if gz in px and gz != cid:
        look = 1.0 if px[gz] > px[cid] else -1.0
        p["head"][2] += 0.8 * look
    elif speaker and cid != speaker and speaker in px:            # dinleyen konuşana bakar
        look = 1.0 if px[speaker] > px[cid] else -1.0
        p["head"][2] += 0.7 * look
    hear = None if spk else listener_reaction.performance(beat, cid, t)
    if hear and hear["speaker"] in px:                           # dinleyici oyunculuğu: replik bitince de konuşandan kopmaz, baş hareketiyle karşılık verir
        if not (gz in px and gz != cid) and speaker is None:
            look = 1.0 if px[hear["speaker"]] > px[cid] else -1.0
            p["head"][2] += listener_reaction.TURN * look * hear["weight"]
        p["head"][0] += hear["nod"]
    if spk:                                                      # vurgulu hecede baş, kaş, el
        p["head"][0] += 0.14 * E
        p["z"] += 0.012 * Hm * E
        p["aR"][1] = (p["aR"][1] if p["aR"][1] else -0.2) - 0.5 * E
    return p, m, look, E if spk else 0.0


def objects_at(plan, designs, t):
    """O anın nesneleri (frame ile aynı hesap; kamera ve çizim yok): {anahtar: (x, y, durum, sahip, el)}; gizlenen nesne yazılmaz."""
    beat = next((b for b in plan["beats"] if b["t_start"] <= t < b["t_end"]), None)
    if beat is None:
        return None
    items = poses_at(plan, designs, t)
    memo = {}

    def items_at(t_):
        if t_ not in memo:
            memo[t_] = poses_at(plan, designs, beat["t_start"] + t_) or items
        return memo[t_]
    out = {}
    for k, (ob, x, y, st, own, hand) in enumerate(_objects_now(beat, items, t - beat["t_start"], items_at)):
        out[ob.get("id") or f"{ob.get('prop', 'obj')}#{k}"] = (x, y, st["state"], own, hand)
    return out


def poses_at(plan, designs, t):
    """O anın çizilecek oyuncu pozları (frame ile aynı hesap; çizim yapılmaz)."""
    return frame(plan, designs, t, poses_only=True)


def group_framing(beat, designs, xs, preset, ph):
    """Genel/orta planın kadrajı (cx, cy, zoom): bütün oyuncular sığar, en uzunun başı üstten kesilmez."""
    cx = sum(xs) / len(xs) if xs else 0.0
    fh = designs[beat["focus"]]["height"] if beat.get("focus") in designs else 1.1
    zoom = ZOOM[preset] * (1.0 + 0.05 * ph)
    cy = 0.95 if preset == "wide" else min(0.85, fh * 0.62 + 0.25)     # orta planda çocuk için kamera alçalır (bacak değil gövde+yüz)
    if len(xs) > 1:                                                     # kadraj güvenliği: tüm oyuncular kadraja sığsın
        lo, hi = min(xs), max(xs); half = (hi - lo) / 2 + 0.7
        zoom = max(0.8, min(zoom, 5.12 / (2 * half))); cx = (lo + hi) / 2
    cy, zoom = head_safe_framing(cy, zoom, max((designs[c]["height"] for c in beat["cast"]), default=0.0), sc.BASE_PPM)
    return cx, cy, zoom


def close_base(preset, design, ph=0.0, E=0.0):
    """Yakın planın kırpma güvenliğinden ÖNCEKİ (cy, zoom) değeri."""
    zoom = ZOOM[preset] * (1.0 + 0.05 * ph) * (1.0 + 0.18 * E if preset == "close" else 1.0)   # vurguda kamera içeri vurur
    if design["height"] > 1.3:
        zoom *= 0.78                                    # yetişkin yakın planda ekranı doldurmasın: kadraj biraz açılır
    return design["height"] * 0.80, zoom


def close_tightness(plan, designs, preset, focus, run, needs):
    """Bu yakın çekim grup planından kaç kat dar: (yakın ölçek / aynı anın orta plan ölçeği, kırpma kipi).
    Çekim boyunca TEK değerdir (çekimin ilk anı, yaklaşma ve vurgu olmadan): plan türü çekimin ortasında değişemez."""
    beat, a, _b = run[0]
    dur = beat["t_end"] - beat["t_start"]
    xs = [sm.motion_x(beat["motion"][c], a, dur, designs[c]["height"]) for c in beat["cast"]]
    cy, zoom = close_base(preset, designs[focus])
    _cy, zoom, crop = crop_safe_framing(cy, zoom, designs[focus], sc.BASE_PPM, needs)
    return zoom / group_framing(beat, designs, xs, "medium", 0.0)[2], crop


def camera_raw(plan, designs, beat, t, items):
    """t anının TEK BAŞINA kadraj kararı (geçiş uygulanmadan): {'cam','preset','focus','crop','reaction','rule','opened_from'}.
    'rule' kadrajı üreten kuralın kimliğidir: aynı kural içinde kadraj sürekli değişir; farklı kurallar arasındaki geçişi soft_camera denetler."""
    lt, dur = t - beat["t_start"], beat["t_end"] - beat["t_start"]
    xs = [it[2]["x"] for it in items]
    speaker = speaker_at(beat, t)
    sp_ln = next((ln for ln in beat["lines"] if ln["char"] == speaker and ln["start"] <= t < ln["end"]), None)
    E = emphasis(sp_ln.get("cues", []), t - sp_ln["start"]) if speaker else 0.0
    avg = sum(xs) / len(xs) if xs else 0.0
    chosen = chosen_shot(plan, beat, t)
    preset, focus, ph, src_lt = (chosen[k] for k in ("preset", "focus", "ph", "src_lt"))
    reaction = reaction_target(beat, t)
    reaction = reaction if preset in CLOSE_PRESETS and reaction == focus else None
    act_ = action_staging.framing(beat, designs, src_lt, sc.BASE_PPM) if preset == "action" else None      # temas penceresi: sabit aksiyon kadrajı (tepki/yakın plan/ek plan kesmesi yapılmaz)
    out = {"focus": focus, "crop": None, "reaction": reaction, "opened_from": None, "src_lt": src_lt}
    if act_:
        return dict(out, cam=sc.Cam(act_["cx"], act_["cy"], act_["zoom"]), preset="action", rule=("action",))
    if preset == "point":
        pt_ = pointing.framing(beat, designs, src_lt, sc.BASE_PPM)
        if pt_:
            return dict(out, cam=sc.Cam(pt_["cx"], pt_["cy"], pt_["zoom"]), preset="point", rule=("point",))
    if preset in CLOSE_PRESETS and focus in designs:        # yakın plan: alt kenar ya ayak zeminini gösterir ya kasıtlı olarak üst bedenden keser
        run = close_run(plan, beat, lt, (preset, focus))
        ph = run_phase(run, beat, lt)
        needs = shot_needs(plan, designs, focus, run)
        ratio, crop0 = close_tightness(plan, designs, preset, focus, run, needs)
        if crop0 == "full" and ratio < shot_cuts.CUT_ZOOM_RATIO:   # tam boya açılan ve grup planından gerçek kesme kadar dar olmayan plan 'yakın' değildir: dürüstçe orta plan
            cx, cy, zoom = group_framing(beat, designs, xs, "medium", ph)
            return dict(out, cam=sc.Cam(cx, cy, zoom), preset="medium", rule=("opened", focus), opened_from=preset)
        fx = xs[beat["cast"].index(focus)] if focus in beat["cast"] else avg
        E_cam = E * follow_steadiness(beat, designs, focus, lt) if focus == speaker else 0.0     # vurgu itmesi yalnız duran KONUŞANIN planında: takip planı ve dinleyen planı nabız gibi atmaz
        cy, zoom = close_base(preset, designs[focus], ph, E_cam)
        cy, zoom, crop = crop_safe_framing(cy, zoom, designs[focus], sc.BASE_PPM, needs, ph, E_cam if preset == "close" else 0.0)
        return dict(out, cam=sc.Cam(fx, cy, zoom), preset=preset, crop=crop, rule=("close", preset, focus))
    if preset in shot_cuts.GROUP:
        cx, cy, zoom = group_framing(beat, designs, xs, preset, ph)
        return dict(out, cam=sc.Cam(cx, cy, zoom), preset=preset, rule=("group",))
    if preset == "insert" and beat.get("props"):
        ix, iy = props2d.place(beat["props"][0], xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
        cam = sc.Cam(ix, max(0.55, min(iy - 0.35, 1.0)), 1.05)      # ek plan: nesne + karakterler birlikte kadrajda (başsız/bacaksız kadraj yok)
    else:
        fh = designs[focus]["height"] if focus in designs else 1.1
        cam = sc.Cam(avg, fh * 0.80, ZOOM.get(preset, 1.5) * (1.0 + 0.05 * ph))
    return dict(out, cam=cam, preset=preset, rule=(preset,))


def _decision_key(plan, beat, t):
    """Kadraj kuralının değişebileceği anları bulmak için ucuz veri anahtarı (poz hesabı yok)."""
    c = chosen_shot(plan, beat, t)
    return c["preset"], c["focus"], c["window"]


def _timeline(plan):
    return sorted(list(plan.get("context") or []) + list(plan["beats"]), key=lambda b_: b_["t_start"])


def _changes_before(plan, beat, t):
    """t'den geriye, en çok SOFT_MAX_S içinde, kadraj kuralının değişmiş olabileceği anlar (yeniden eskiye): [(an, önceki vuruş, sonraki vuruş)].
    Gerçek kesmede (sahne/mekân/kadro değişimi) durur. Plan penceresi dışındaki sürekli komşular plan['context'] verisindedir."""
    order = _timeline(plan)
    i = next((n for n, b_ in enumerate(order) if b_ is beat), None)
    limit, cur, hi = t - shot_cuts.SOFT_MAX_S, beat, t
    key = _decision_key(plan, cur, hi)
    while hi > limit:
        lo = max(cur["t_start"], hi - CHOICE_STEP_S)
        k = _decision_key(plan, cur, lo)
        if k != key:
            a, b = lo, hi
            while b - a > 1e-5:                            # sınır ikiye bölerek bulunur
                m = (a + b) / 2
                a, b = (m, b) if _decision_key(plan, cur, m) == k else (a, m)
            yield b, cur, cur
        key, hi = k, lo
        if hi <= cur["t_start"] + 1e-9:
            prev = order[i - 1] if i else None
            if prev is None or not shot_cuts.continues(prev, cur):
                return
            at = cur["t_start"]
            yield at, prev, cur
            cur, i, hi = prev, i - 1, at - 1e-5
            key = _decision_key(plan, cur, hi)


def soft_camera(plan, designs, beat, t, items, _memo=None):
    """camera_raw + yakın kadrajlar arası sürekli geçiş. İki FARKLI kural gerçek kesme eşiğini geçemiyorsa (shot_cuts.is_real_cut)
    kamera tek karede atlamaz: değişim anındaki kadrajdan yeni kuralın kadrajına yumuşak geçer. Aynı kuralın içindeki sıçrama
    YUMUŞATILMAZ (kurgu/kamera hatasıdır; atlama ölçüsü ve render kapısı yakalar). Çıktıdaki 'soft': geçişin ilerlemesi 0..1 ya da None."""
    memo = {} if _memo is None else _memo
    now = dict(camera_raw(plan, designs, beat, t, items), soft=None)

    def view(beat_, t_):
        return dict(plan, beats=[beat_])

    def poses(beat_, t_):
        return poses_at(view(beat_, t_), designs, t_)
    for tb, before, after in _changes_before(plan, beat, t):
        if (before["i"], round(tb, 4)) not in memo:
            t0 = min(tb - 1e-5, before["t_end"] - 1e-5)
            its0 = poses(before, t0)
            raw0 = camera_raw(plan, designs, before, t0, its0)
            raw1 = camera_raw(plan, designs, after, tb, poses(after, tb))
            memo[(before["i"], round(tb, 4))] = (t0, its0, raw0, raw1)
        t0, its0, raw0, raw1 = memo[(before["i"], round(tb, 4))]
        if raw0["rule"] == raw1["rule"]:
            continue
        old = soft_camera(plan, designs, before, t0, its0, memo)["cam"]      # geçiş sürerken yeni değişim gelirse ekrandaki kadrajdan devam edilir
        new = raw1["cam"]
        zr, dx, dy = new.s / old.s, new.x(old.cx) - pp.W / 2, new.y(old.cy) - pp.H / 2
        if shot_cuts.is_real_cut(zr, dx, dy, shot_cuts.JOIN_MARGIN):
            return now
        u = (t - tb) / shot_cuts.soft_seconds(zr, dx, dy)
        if u >= 1.0:
            return now
        w, c = pp_smooth(u), now["cam"]
        now["cam"] = sc.Cam(old.cx + (c.cx - old.cx) * w, old.cy + (c.cy - old.cy) * w, old.z * (c.z / old.z) ** w)
        now["soft"] = round(max(0.0, u), 3)
        return now
    return now


def frame(plan, designs, t, bible_chars=None, trace=None, poses_only=False, camera_only=False):
    """trace (dict) verilirse çizimin GERÇEK yerleşimi yazılır: kamera, pozlar ve çizim sırasıyla katmanlar [(tür, kimlik, çizici(cv, cam), nokta)].
    Okunabilirlik ölçüsü bu kayıttan çalışır; ayrı bir yerleşim tahmini yapılmaz.
    camera_only=True: çizim yapmadan aynı kamera kararını ve çizilecek oyuncuları döner (kadraj kapısı için)."""
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
        p, m, look, e_ = actor_pose(plan, designs, beat, cid, t, px)
        items.append((cid, designs[cid], p, m, look, e_))
        xs.append(p["x"])
    apply_hand_swap(beat, items, lt)                     # önceki vuruştan başka elde gelen nesne görünür biçimde el değiştirir
    apply_throw_swing(beat, items, lt)                   # atışta kol savurma
    apply_handoff_reach(beat, items, lt)                 # el değiştirmede eller buluşma noktasına uzanır
    pointing.apply(beat, designs, items, lt)             # hedefli gösterme jesti: kol hedefe uzanır
    if poses_only:
        return items
    _memo = {}

    def items_at_(t_, _b=beat):                          # aynı vuruşta başka bir anın pozları (atışın bırakma noktası)
        if t_ not in _memo:
            _memo[t_] = poses_at(plan, designs, _b["t_start"] + t_) or items
        return _memo[t_]
    view_ = soft_camera(plan, designs, beat, t, items)
    cam, preset, focus, crop, reaction = (view_[k] for k in ("cam", "preset", "focus", "crop", "reaction"))
    act_ids_ = {c for ev_ in action_staging._events(beat) for c in (ev_["by"], ev_.get("to")) if c} if preset == "action" else set()
    if preset == "point":                       # gösterme kadrajının katılanları: gösteren ve gösterilen oyuncu
        its_ = pointing.window_at(beat, view_["src_lt"])[2]
        act_ids_ = {c for it_ in its_ for c in (it_["by"], it_.get("to") if isinstance(it_.get("to"), str) else None) if c}

    def skipped_(cid_, d_, p_):      # yakın planda odak dışı karakterin yüzü kenarda yarım kesilecekse çizilmez (kazara kesik yüz yok)
        return ((preset in ("close", "xclose") and cid_ != focus) or (preset in ("action", "point") and cid_ not in act_ids_)) and _head_cropped(cam, p_["x"], d_["height"])
    if camera_only:
        if trace is not None:
            trace.update(cam=cam, preset=preset, crop=crop, focus=focus, items=items, beat=beat, lt=lt, items_at=items_at_,
                         opened_from=view_["opened_from"], soft=view_["soft"],
                         drawn=[i[0] for i in items if not skipped_(i[0], i[1], i[2])])
        return None
    cv = pp.Cv()
    layers = [] if trace is not None else None
    states = {} if trace is not None else None
    emit = (lambda kind_, key_, fn_, at_=None: layers.append((kind_, key_, fn_, at_))) if trace is not None else None
    sc.scene_back(cv, beat["scene"], cam, t, light=beat.get("light", ""))
    if _prof().get("dust", True):                       # ayak tozu + hız çizgisi: zemine ait, dekor parçalarının ARKASINDA (hedefin önünü örtmez)
        for cid_, d_, _p, m_, _lk, _e in items:
            if m_["kind"] not in ("walk", "run"):       # yönetmen tepkisi/uzanma yürüyüşü kestiyse toz da biter
                continue
            plan_ = fx_layer.dust_plan(beat["motion"][cid_], lt, dur, d_["height"])
            fx_layer.dust(cv, cam, plan_, t, d_["height"])
    if preset != "insert":
        setpieces2d.draw(cv, cam, beat.get("loc"), t, pieces=beat.get("pieces"))
    if bg_art is not None:
        try:
            bg_art.enhance(cv, beat["scene"], beat.get("light"), t)
        except Exception:      # boyama katmanı kare üretimini asla düşürmesin
            pass
    for k_, kind in enumerate(beat.get("props") or []):             # arka katman nesneleri (yaprak, damla) karakterlerden ÖNCE çizilir: yüzlerin üstüne binmez
        if kind in BACK_PROPS and preset != "insert":
            wx, wy = props2d.place(kind, xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
            props2d.draw(cv, cam, kind, wx, wy, t, k_)
    for cid, d, p, m, look, e in action_staging.draw_order(beat, designs, items):
        if skipped_(cid, d, p):
            continue
        emo = EMO.get(m["kind"], "neutral")
        mood_ = spk_mood.get(cid) or beat.get("mood", "neutral")
        if emo == "neutral" and mood_ != "neutral":
            emo = mood_
        hear = listener_reaction.performance(beat, cid, t) if cid != speaker else None
        brow_ = e
        if hear and hear["emotion"]:
            brow_ = max(e, hear["brow"])
            if m["kind"] not in EMO:                                   # kendi eylem duygusu (gülme, şaşırma...) varsa o korunur
                emo = hear["emotion"]
        slot = int(t / 1.6 + m["seed"])
        dart = (_hash(slot, m["seed"], 3) - 0.5) * 1.4
        gaze_ = look * 0.9 + (0 if look else dart)
        if hear and hear["speaker"] in px and hear["emotion"]:          # dinleyen göz gezdirmez: konuşana bakar
            gaze_ = 0.9 if px[hear["speaker"]] > p["x"] else -0.9
        watch = action_look(beat, lt)
        if watch:                                                      # eylem sürerken herkes hedefe / eli işleyen ortağa bakar
            if watch[0] == "x":
                tx_ = watch[1]
            else:
                others_ = [px[c] for c in watch[1] if c != cid and c in px]
                tx_ = others_[0] if others_ else None
            if tx_ is not None and abs(tx_ - p["x"]) > 0.05:
                gaze_ = 0.9 if tx_ > p["x"] else -0.9
        blink_, open_ = eyes_state(emo, lt, m["seed"], blink_at(t, m["seed"]), bool(watch) or bool(hear and cid == reaction_target(beat, t)))     # tepki planındaki yüz gözü kapalı yakalanmaz
        st = {"mouth": letters.get(cid, "X"), "blink": blink_, "emotion": emo, "eyes_open": open_,
              "gaze": gaze_, "brow": brow_, "pulse": e}
        if states is not None:
            states[cid] = dict(st, watching=watch)
        body_ = lambda c, cm, d_=d, p_=p, st_=st: pp.draw_character(c, d_, p_, st_, cm.x(p_["x"]), cm.y(0.0), cm.s, t)
        body_(cv, cam)
        if emit is not None:
            emit("character", cid, body_, (p["x"], 0.0))
        _draw_objects(cv, cam, beat, items, designs, lt, owner=cid, emit=emit, items_at=items_at_)      # elindeki nesne: karakterden hemen sonra, parmaklar önde
    if xs:
        fx_layer.icons(cv, cam, beat, xs, [designs[c]["height"] for c in beat["cast"]], t, lt)
    _draw_objects(cv, cam, beat, items, designs, lt, emit=emit, items_at=items_at_)             # serbest nesneler (yerde, uçuşta)
    _draw_objects(cv, cam, beat, items, designs, lt, owner="__late__", emit=emit, items_at=items_at_)   # el değiştiren nesne: tüm karakterlerden sonra
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
        trace.update(cam=cam, preset=preset, crop=crop, focus=focus, items=items, layers=layers, states=states, beat=beat, lt=lt,
                     opened_from=view_["opened_from"], soft=view_["soft"])
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
ENGINE_FILES = ("render2d.py", "puppet2d.py", "scenes2d.py", "setpieces2d.py", "props2d.py", "fx_layer.py", "bg_art.py", "shot_motion.py", "puppet_side.py", "object_state.py", "pose_blend.py",
                "shot_planner.py", "style_profile.py", "mood_engine.py", "action_staging.py", "staging.py", "continuity.py", "listener_reaction.py", "shot_cuts.py",
                "pointing.py")


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
