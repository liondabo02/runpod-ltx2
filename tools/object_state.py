"""Nesne durum makinesi (saf Python, çizimden bağımsız). Nesne izi (track) = zaman sıralı anahtar kareler:
  {"t":..,"at":[x,y] | "hedef_adi"}  yerde/yerleşik      {"t":..,"holder":"id"[,"hand":"L"|"R"]}  elde      {"t":..,"at":..,"hide":true}  hedefte kaybolur (imha)
Geçişler: yerde→elde = AL, elde→başka elde = VER (el değiştirme), elde→yerde = BIRAK, elde→hedef+hide = İMHA.
Yasak: sırasız zaman, bilinmeyen sahip, aynı sahibe ikinci kez 'al', yerden yere ışınlanma (arada elde olmadan farklı konum), hide sonrası anahtar.
Motorlar: render (konum), hareket (uzanma pencereleri, ağırlık pozu), ses (temas olayları SFX'e), QA (süreklilik ölçümü)."""
import math

# Nesne kataloğu: ağırlık (kg-benzeri), boy (m, çizim ölçeği 0.55 ile), tutuş yüksekliği (tabandan, m), taşıma biçimi ipucu
PROPS = {
    "bottle": {"w": 0.4, "len": 0.31, "grip": 0.12}, "stone": {"w": 2.5, "len": 0.25, "grip": 0.08}, "shovel": {"w": 1.8, "len": 1.30, "grip": 0.55},
    "hat": {"w": 0.1, "len": 0.20, "grip": 0.02}, "flower": {"w": 0.1, "len": 0.40, "grip": 0.10}, "seed": {"w": 0.05, "len": 0.12, "grip": 0.05},
    "mic": {"w": 0.3, "len": 0.25, "grip": 0.08}, "balloon": {"w": 0.02, "len": 0.50, "grip": 0.02}, "lantern": {"w": 0.8, "len": 0.35, "grip": 0.25},
    "kite": {"w": 0.1, "len": 0.80, "grip": 0.05},
}
WEIGHT = {k: v["w"] for k, v in PROPS.items()}


def weight_of(prop):
    return PROPS.get(prop, {}).get("w", 0.5)


def grip_of(prop, scale=0.55):
    """Tutuş noktasının nesne tabanından yüksekliği (m), çizim ölçeğiyle."""
    return PROPS.get(prop, {}).get("grip", 0.1) * scale / 0.55


def carry_style(prop, hand_count=1):
    """Taşıma biçimi: ağırlık ve boydan. 'one_hand' (yan), 'two_hand_front' (önde iki el, ağır), 'shoulder' (uzun alet omuzda/yanda)."""
    p = PROPS.get(prop, {"w": 0.5, "len": 0.3})
    if p["len"] >= 0.9:
        return "shoulder"
    if p["w"] >= 1.5:
        return "two_hand_front"
    return "one_hand"


def carry_adjust(weight, style="one_hand", reach=0.25):
    """Ağırlık merkezi ve denge: yük gövdeden ne kadar önde/yanda (reach, m) ve ne kadar ağır -> karşı denge.
    one_hand: yük yanda -> gövde karşı yana yaslanır (lean küçük, omuz çökmesi sq), tek kol dolu;
    two_hand_front: yük önde -> belirgin geri yaslanma + iki kol önde + yavaşlama;
    shoulder: yük omuzda -> hafif öne eğilme, kol yukarıda. Dönen alanlar puppet pose'una EKLENİR; 'arms' hangi kol pozunun uygulanacağını söyler."""
    k = max(0.0, min(1.0, weight / 3.0))
    if style == "two_hand_front":
        return {"lean": -0.16 * k * (reach / 0.25), "sq": -0.05 * k, "head_nod": 0.08 * k, "speed": 1.0 - 0.35 * k, "arms": "both_front", "side_tilt": 0.0}
    if style == "shoulder":
        return {"lean": 0.05 * k, "sq": -0.02 * k, "head_nod": 0.02 * k, "speed": 1.0 - 0.15 * k, "arms": "one_up", "side_tilt": 0.0}
    return {"lean": -0.04 * k, "sq": -0.03 * k, "head_nod": 0.03 * k, "speed": 1.0 - 0.18 * k, "arms": "one_side", "side_tilt": 0.10 * k}


def _same_place(a, b, targets, tol=0.05):
    def xy(k):
        at = k["at"]
        return tuple(targets[at]) if isinstance(at, str) else tuple(at)
    try:
        pa, pb = xy(a), xy(b)
    except KeyError:
        return False
    return abs(pa[0] - pb[0]) <= tol and abs(pa[1] - pb[1]) <= tol


def validate(track, cast=None, targets=None, sinks=None):
    """Sorun listesi döner (boş = geçerli)."""
    targets = targets or {}; sinks = sinks or set(); probs = []
    if not track:
        return ["iz boş"]
    ts = [k.get("t") for k in track]
    if any(not isinstance(t, (int, float)) for t in ts):
        return ["anahtar karede t yok"]
    if any(b < a for a, b in zip(ts, ts[1:])):
        probs.append("zaman sırasız")
    hidden_at = None
    for i, k in enumerate(track):
        if hidden_at is not None:
            probs.append(f"hide sonrası anahtar (t={k['t']})"); break
        if ("holder" in k) == ("at" in k):
            probs.append(f"anahtar {i}: tam olarak biri gerekli: holder veya at")
            continue
        if k.get("holder") and cast is not None and k["holder"] not in cast:
            probs.append(f"anahtar {i}: bilinmeyen sahip '{k['holder']}'")
        if isinstance(k.get("at"), str) and k["at"] not in targets:
            probs.append(f"anahtar {i}: bilinmeyen hedef '{k['at']}'")
        if k.get("hide"):
            hidden_at = k["t"]
            if "at" not in k:
                probs.append("hide yalnız hedef (at) anahtarında")
            elif not (isinstance(k["at"], str) and k["at"] in sinks):
                probs.append(f"anahtar {i}: imha yalnız tanımlı bir hedefte (çöp kutusu vb.) olabilir; '{k['at']}' imha hedefi değil")
        elif "at" in k and not isinstance(k["at"], str) and not k.get("surface") and len(k["at"]) > 1 and k["at"][1] > 0.05:
            probs.append(f"anahtar {i}: nesne havada bırakılıyor (y={k['at'][1]}) ve yüzey tanımı yok")
        if i:
            a = track[i - 1]
            if "at" in a and "at" in k and not _same_place(a, k, targets) and not k.get("hide"):
                probs.append(f"anahtar {i}: elde olmadan farklı konuma geçiş (ışınlanma/kayma)")
            if "holder" in a and "holder" in k and a["holder"] != k["holder"] and k["t"] - a["t"] < 0.2:
                probs.append(f"anahtar {i}: el değiştirme çok kısa ({k['t']-a['t']:.2f}s < 0.2s)")
    return probs


def state_at(track, lt):
    """O andaki durum: {'state': ground|held|transfer|put|hidden, 'holder', 'to', 'u'}."""
    if lt < track[0]["t"]:
        k = track[0]; return {"state": "held" if "holder" in k else "ground", "holder": k.get("holder"), "to": None, "u": 0.0}
    for a, b in zip(track, track[1:]):
        if a["t"] <= lt <= b["t"]:
            u = 0.0 if b["t"] == a["t"] else (lt - a["t"]) / (b["t"] - a["t"])
            if "holder" in a and "holder" in b:
                if a["holder"] == b["holder"]:
                    return {"state": "held", "holder": a["holder"], "to": None, "u": u}
                return {"state": "transfer", "holder": a["holder"], "to": b["holder"], "u": u}
            if "holder" in a:                                           # elde → yere/hedefe
                if b.get("hide") and lt >= b["t"]:
                    return {"state": "hidden", "holder": None, "to": None, "u": 1.0}
                return {"state": "put", "holder": a["holder"], "to": None, "u": u}
            if "holder" in b:                                           # yerde → ele
                return {"state": "pickup", "holder": None, "to": b["holder"], "u": u}
            return {"state": "ground", "holder": None, "to": None, "u": u}
    k = track[-1]
    if k.get("hide"):
        return {"state": "hidden", "holder": None, "to": None, "u": 1.0}
    return {"state": "held" if "holder" in k else "ground", "holder": k.get("holder"), "to": None, "u": 1.0}


def events(track):
    """Temas olayları (SFX ve hareket motoru için): AL, VER, BIRAK, IMHA. t = temasın tamamlandığı an."""
    ev = []
    for a, b in zip(track, track[1:]):
        if "at" in a and "holder" in b:
            ev.append({"type": "pickup", "t": b["t"], "by": b["holder"], "t_start": a["t"]})
        elif "holder" in a and "holder" in b and a["holder"] != b["holder"]:
            ev.append({"type": "handoff", "t": b["t"], "by": a["holder"], "to": b["holder"], "t_start": a["t"]})
        elif "holder" in a and "at" in b:
            ev.append({"type": "dispose" if b.get("hide") else "drop", "t": b["t"], "by": a["holder"], "t_start": a["t"]})
    return ev


def reach_windows(track, lead=0.6):
    """Hareket motoru için uzanma pencereleri: (karakter, başlangıç, bitiş, tür). Alıcı ve verici uzanır; hazırlık = lead sn önce."""
    w = []
    for e in events(track):
        if e["type"] == "pickup":
            w.append({"actor": e["by"], "t0": max(0.0, e["t"] - lead), "t1": e["t"], "kind": "pickup"})
        elif e["type"] == "handoff":
            w.append({"actor": e["by"], "t0": max(0.0, e["t_start"]), "t1": e["t"], "kind": "give"})
            w.append({"actor": e["to"], "t0": max(0.0, e["t"] - lead), "t1": e["t"], "kind": "take"})
        elif e["type"] in ("drop", "dispose"):
            w.append({"actor": e["by"], "t0": max(0.0, e["t"] - lead), "t1": e["t"], "kind": e["type"]})
    return w


def position(track, lt, hold_fn, target_fn, arc=0.12):
    """Nesnenin dünya konumu (x, y, durum). hold_fn(holder, lt) -> (x, y) elin konumu; target_fn(at) -> (x, y).
    El değiştirme ve bırakma yay çizer; yay yüksekliği mesafeyle orantılı (kısa mesafede küçük)."""
    def pos(k):
        return hold_fn(k["holder"], lt, k.get("hand")) if "holder" in k else target_fn(k["at"])
    st = state_at(track, lt)
    if st["state"] == "hidden":
        return None, None, st
    if lt <= track[0]["t"]:
        p = pos(track[0]); return p[0], p[1], st
    if lt >= track[-1]["t"]:
        p = pos(track[-1]); return p[0], p[1], st
    for a, b in zip(track, track[1:]):
        if a["t"] <= lt <= b["t"]:
            pa, pb = pos(a), pos(b)
            u = 0.0 if b["t"] == a["t"] else (lt - a["t"]) / (b["t"] - a["t"]); u = u * u * (3 - 2 * u)
            moving = ("holder" in a) != ("holder" in b) or a.get("holder") != b.get("holder") or ("at" in a and "at" in b and a["at"] != b["at"])
            dist = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            lift = min(arc, 0.25 * dist + 0.03) * math.sin(math.pi * u) if moving else 0.0
            return pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u + lift, st
    p = pos(track[-1]); return p[0], p[1], st


def max_jump(track, hold_fn, target_fn, fps=24, t0=None, t1=None):
    """Kare-kare en büyük konum sıçraması (metre). Ölçü: nesne ışınlanıyor mu? Elde taşırken el hızından büyük sıçrama = kusur."""
    t0 = track[0]["t"] if t0 is None else t0; t1 = track[-1]["t"] if t1 is None else t1
    prev = None; worst = 0.0; at = 0.0
    for i in range(int((t1 - t0) * fps) + 1):
        t = t0 + i / fps
        x, y, st = position(track, t, hold_fn, target_fn)
        if x is None:
            prev = None; continue
        if prev is not None:
            d = math.hypot(x - prev[0], y - prev[1])
            if d > worst: worst, at = d, t
        prev = (x, y)
    return worst, at


def continuity(track, hold_fn, target_fn, fps=24, margin=1.25):
    """Hız/konum sürekliliği (FPS, mesafe ve süreye göre): her aralıkta kare başına adım, o aralığın beklenen hız sınırıyla karşılaştırılır.
    Sınır = (iki uç noktanın en yüksek hızı + 1.6 * yol/süre + yay payı) * margin. Anahtar karelerde dünya hızı süreksizliği de ölçülür.
    Dönen: {'ok', 'worst_ratio', 'at', 'key_vel_jump'} — worst_ratio 1'i aşarsa o aralıkta sıçrama var."""
    def P(k, t):
        return hold_fn(k["holder"], t, k.get("hand")) if "holder" in k else target_fn(k["at"])
    dt = 1.0 / fps; worst = 0.0; at = 0.0; vel = {}
    for a, b in zip(track, track[1:]):
        D = b["t"] - a["t"]
        if D <= 0:
            continue
        n = max(2, int(D * fps)); ts = [a["t"] + D * i / n for i in range(n + 1)]
        pa = [P(a, t) for t in ts]; pb = [P(b, t) for t in ts]
        hs = max(max(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(s, s[1:])) / (D / n) for s in (pa, pb))
        L = max(math.hypot(x[0] - y[0], x[1] - y[1]) for x, y in zip(pa, pb))
        moving = ("holder" in a) != ("holder" in b) or a.get("holder") != b.get("holder") or ("at" in a and "at" in b and a["at"] != b["at"])
        arc = (min(0.12, 0.25 * L + 0.03) * 2.0 / D) if moving else 0.0
        bound = ((hs + (1.6 * L / D if moving else 0.0) + arc) * margin) * (D / n) + 1e-6
        prev = None
        for t in ts:
            x, y, st = position(track, t, hold_fn, target_fn)
            if x is None:
                prev = None; continue
            if prev is not None:
                r = math.hypot(x - prev[0], y - prev[1]) / bound
                if r > worst:
                    worst, at = r, t
            prev = (x, y)
    kvj = 0.0
    for k in track[1:-1]:
        t = k["t"]
        p0 = position(track, t - 2 * dt, hold_fn, target_fn); p1 = position(track, t - dt, hold_fn, target_fn)
        p2 = position(track, t + dt, hold_fn, target_fn); p3 = position(track, t + 2 * dt, hold_fn, target_fn)
        if None in (p0[0], p1[0], p2[0], p3[0]):
            continue
        v_in = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / dt; v_out = math.hypot(p3[0] - p2[0], p3[1] - p2[1]) / dt
        kvj = max(kvj, abs(v_out - v_in))
    return {"ok": worst <= 1.0, "worst_ratio": round(worst, 3), "at": round(at, 3), "key_vel_jump": round(kvj, 3)}
