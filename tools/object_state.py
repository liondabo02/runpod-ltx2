"""Nesne durum makinesi (saf Python, çizimden bağımsız). Nesne izi (track) = zaman sıralı anahtar kareler:
  {"t":..,"at":[x,y] | "hedef_adi"}  yerde/yerleşik      {"t":..,"holder":"id"[,"hand":"L"|"R"]}  elde      {"t":..,"at":..,"hide":true}  hedefte kaybolur (imha)
Geçişler: yerde→elde = AL, elde→başka elde = VER (el değiştirme), elde→yerde = BIRAK, elde→hedef+hide = İMHA.
Yasak: sırasız zaman, bilinmeyen sahip, aynı sahibe ikinci kez 'al', yerden yere ışınlanma (arada elde olmadan farklı konum), hide sonrası anahtar.
Motorlar: render (konum), hareket (uzanma pencereleri, ağırlık pozu), ses (temas olayları SFX'e), QA (süreklilik ölçümü)."""
import math

WEIGHT = {"bottle": 0.4, "stone": 2.5, "shovel": 1.8, "hat": 0.1, "flower": 0.1, "seed": 0.05, "mic": 0.3, "balloon": 0.02, "lantern": 0.8, "kite": 0.1}


def weight_of(prop):
    return WEIGHT.get(prop, 0.5)


def carry_adjust(weight):
    """Ağırlığa göre taşıyıcı poz farkı (puppet pose alanlarına EKLENİR). Hafif: hemen hiç; ağır: geri yaslanma, ezilme, yavaş adım."""
    k = max(0.0, min(1.0, weight / 3.0))
    return {"lean": -0.10 * k, "sq": -0.04 * k, "arm_fwd": 0.0 + 0.25 * k, "speed": 1.0 - 0.30 * k, "head_nod": 0.06 * k}


def _same_place(a, b, targets, tol=0.05):
    def xy(k):
        at = k["at"]
        return tuple(targets[at]) if isinstance(at, str) else tuple(at)
    try:
        pa, pb = xy(a), xy(b)
    except KeyError:
        return False
    return abs(pa[0] - pb[0]) <= tol and abs(pa[1] - pb[1]) <= tol


def validate(track, cast=None, targets=None):
    """Sorun listesi döner (boş = geçerli)."""
    targets = targets or {}; probs = []
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
