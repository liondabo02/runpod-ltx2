"""AHOS aksiyon okunabilirliği ölçüsü (genel motor; proje adı/koordinatı bilmez).
Her temas olayı (al / ver / bırak / çöpe at) penceresinde, renderer'ın GERÇEKTEN çizdiği katmanlardan (render2d.frame(trace=...))
piksel maskeleriyle şunlar ölçülür: nesne, temas eden el(ler), oyuncular ve atış/bırakma hedefi KADRAJDA ve ÖRTÜLMEMİŞ mi;
kamera bu pencerede başka yere kesiyor mu (aksiyon kadrajı süreklidir); nesne seçilebilecek kadar büyük mü.
Bu ölçü 'seyirci anladı' demek DEĞİLDİR: yalnız görünürlük/kadraj için gerekli koşulları denetler. Eşikler yapılandırılabilir ve insan izlemesiyle doğrulanmamıştır."""
from PIL import Image, ImageChops, ImageDraw
import object_state
import puppet2d as pp
import scenes2d as sc
import setpieces2d
import render2d as r2

DEFAULTS = {
    "object_visible": 0.60,       # nesne piksellerinin kadrajda + örtülmemiş oranı (örnek başına)
    "hand_visible": 0.60,         # temas eden elin görünür oranı
    "actor_visible": 0.55,        # temasa katılan oyuncunun görünür oranı
    "target_visible": 0.60,       # hedef ağzının (atış/bırakma) görünür oranı
    "pass_ratio": 0.85,           # penceredeki örneklerin en az bu oranı her ölçütü sağlamalı
    "min_object_px": 14,          # nesnenin ekrandaki uzun kenarı (1280x720)
    "max_cuts": 0,                # pencere içinde kamera sıçraması sayısı
    "lead_s": 0.3, "tail_s": 0.3, "fps": 12,
}
SENT = (1, 2, 3)
W, H = pp.W, pp.H


def _mask(draw, cam):
    """Katmanı boş tuvale çiz -> ikili maske (L, 0/255)."""
    cv = pp.Cv(ss=1)
    cv.img.paste(SENT, (0, 0, W, H))
    draw(cv, cam)
    d = ImageChops.difference(cv.img, Image.new("RGB", cv.img.size, SENT))
    r, g, b = d.split()
    return ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v else 0)


def _count(m):
    return m.histogram()[255]


def _minus(a, b):
    return ImageChops.subtract(a, b)


def _disk(cx, cy, r):
    """(kadraj içi maske, toplam alan)"""
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    full = Image.new("L", (int(2 * r) + 4, int(2 * r) + 4), 0)
    ImageDraw.Draw(full).ellipse([2, 2, 2 + 2 * r, 2 + 2 * r], fill=255)
    return m, max(1, _count(full))


def _rect(x0, y0, x1, y1):
    m = Image.new("L", (W, H), 0)
    if min(x1, W) > max(x0, 0) and min(y1, H) > max(y0, 0):
        ImageDraw.Draw(m).rectangle([max(x0, 0), max(y0, 0), min(x1, W) - 1, min(y1, H) - 1], fill=255)
    return m, max(1.0, (x1 - x0) * (y1 - y0))


def _union(masks):
    out = Image.new("L", (W, H), 0)
    for m in masks:
        out = ImageChops.lighter(out, m)
    return out


def action_events(beat):
    """Okunması gereken aksiyonlar: [{'type','object','t','t_start','by','to','target'}]."""
    out = []
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        for e in object_state.events(tr):
            tgt = None
            if e["type"] in ("drop", "dispose"):
                for k in tr:
                    if k.get("t") == e["t"] and isinstance(k.get("at"), str) and k["at"] in (beat.get("targets") or {}):
                        tgt = k["at"]
            out.append(dict(e, object=ob.get("id") or ob.get("prop", "obj"), target=tgt))
    return out


def window(event, dur, cfg=DEFAULTS):
    return max(0.0, event["t_start"] - cfg["lead_s"]), min(dur - 1e-3, event["t"] + cfg["tail_s"])


def sample(plan, designs, beat, event, lt):
    """Tek anın ölçümü: {'object','hand:<id>','actor:<id>','target', 'object_px', 'cam', 'preset'}; ölçülemeyen alan yoktur (None)."""
    tr = {}
    if r2.frame(plan, designs, beat["t_start"] + lt, trace=tr) is None:
        return None
    cam, layers, items = tr["cam"], tr["layers"], {i[0]: i for i in tr["items"]}
    masks = [_mask(fn, cam) for _k, _key, fn, _at in layers]

    def later(i, skip=()):
        return _union([masks[j] for j in range(i + 1, len(layers)) if (layers[j][0], layers[j][1]) not in skip])
    idx = {(k, key): i for i, (k, key, _f, _a) in enumerate(layers)}
    res = {"cam": (cam.cx, cam.cy, cam.z), "preset": tr["preset"]}
    people = [c for c in (event.get("by"), event.get("to")) if c]
    i = idx.get(("object", event["object"]))
    if i is not None:
        _k, _key, fn, at = layers[i]
        centred = sc.Cam(at[0], at[1], cam.z)                      # aynı ölçekte ortalanmış çizim = toplam alan (kadraj dışı pay dahil)
        total = max(1, _count(_mask(fn, centred)))
        seen = _minus(masks[i], later(i, {(lay[0], lay[1]) for lay in layers if lay[0] == "grip"}))     # tutan parmaklar 'örtme' sayılmaz
        res["object"] = min(1.0, _count(seen) / total)
        bb = _mask(fn, centred).getbbox()
        res["object_px"] = max(bb[2] - bb[0], bb[3] - bb[1]) if bb else 0
    elif lt < event["t"] - 1e-6:
        res["object"] = 0.0; res["object_px"] = 0                    # olay bitmeden nesne hiç çizilmiyorsa görünmüyor demektir
    for c in people:
        if c not in items:
            res[f"actor:{c}"] = 0.0; res[f"hand:{c}"] = 0.0
            continue
        _c, d, p, *_ = items[c]
        j = idx.get(("character", c))
        if j is None:                                               # kadraj kuralı bu oyuncuyu çizmedi
            res[f"actor:{c}"] = 0.0; res[f"hand:{c}"] = 0.0
            continue
        centred = sc.Cam(p["x"], d["height"] * 0.5, cam.z)
        total = max(1, _count(_mask(layers[j][2], centred)))
        res[f"actor:{c}"] = min(1.0, _count(_minus(masks[j], later(j))) / total)
        dx, hh = pp.hand_offset(d, p, r2.pick_hand(beat, c))
        disk, area = _disk(cam.x(p["x"] + dx), cam.y(hh), max(3.0, 0.045 * d["height"] * cam.s))
        top = max([k for k, lay in enumerate(layers) if lay[0] == "grip" and lay[1] == c] + [j])     # elde nesne varsa parmaklar sonradan yeniden çizilir
        occ = _union([masks[k] for k in range(top + 1, len(layers)) if layers[k][0] in ("character", "front") and layers[k][1] != c])
        res[f"hand:{c}"] = min(1.0, _count(_minus(disk, occ)) / area)
    if event.get("target"):
        tx, ty = beat["targets"][event["target"]]
        rect, area = _rect(cam.x(tx - 0.2), cam.y(ty + 0.08), cam.x(tx + 0.2), cam.y(ty * 0.55))          # hedefin ağzı/üst yarısı
        occ = _union([masks[k] for k in range(len(layers)) if layers[k][0] in ("character", "front")])
        res["target"] = min(1.0, _count(_minus(rect, occ)) / area)
    return res


def _cuts(samples):
    """Ardışık örnekler arasında kamera sıçraması (kesme): ölçek %12'den ya da merkez 0.25 m'den fazla değişirse."""
    n = 0
    for (_a, a), (_b, b) in zip(samples, samples[1:]):
        (x0, y0, z0), (x1, y1, z1) = a["cam"], b["cam"]
        if abs(z1 - z0) / max(z0, 1e-6) > 0.12 or abs(x1 - x0) > 0.25 or abs(y1 - y0) > 0.25:
            n += 1
    return n


def measure_event(plan, designs, beat, event, cfg=None):
    cfg = dict(DEFAULTS, **(cfg or {}))
    dur = beat["t_end"] - beat["t_start"]
    a, b = window(event, dur, cfg)
    n = max(2, int(round((b - a) * cfg["fps"])) + 1)
    samples = []
    for k in range(n):
        lt = a + (b - a) * k / (n - 1)
        s = sample(plan, designs, beat, event, lt)
        if s is not None:
            samples.append((lt, s))
    metrics, fails = {}, []
    keys = sorted({k for _t, s in samples for k in s if k in ("object", "target") or k.startswith(("hand:", "actor:"))})
    for key in keys:
        vals = [(t, s[key]) for t, s in samples if key in s]
        thr = cfg[key.split(":")[0] + "_visible"]
        good = sum(1 for _t, v in vals if v >= thr) / len(vals)
        wt, wv = min(vals, key=lambda tv: tv[1])
        metrics[key] = {"min": round(wv, 3), "at": round(wt, 2), "ok_ratio": round(good, 3), "samples": len(vals)}
        if good + 1e-9 < cfg["pass_ratio"]:
            fails.append({"metric": key, "why": f"{key} örneklerin yalnız %{100 * good:.0f}'inde >= {thr:.2f} görünür (en kötü {wv:.2f}, vuruş içi {wt:.2f} sn)"})
        # temasın tamamlandığı an ayrıca sağlanmalı (ortalama, kritik anı gizlemesin)
        ct, cs = min(samples, key=lambda ts: abs(ts[0] - event["t_start" if event["type"] in ("dispose", "drop") else "t"]))
        if key in cs and cs[key] < thr and not any(f["metric"] == key for f in fails):
            fails.append({"metric": key, "why": f"{key} kritik anda ({ct:.2f} sn) {cs[key]:.2f} < {thr:.2f}"})
    px = [s["object_px"] for _t, s in samples if s.get("object_px")]
    metrics["object_px"] = min(px) if px else 0
    if metrics["object_px"] < cfg["min_object_px"]:
        fails.append({"metric": "object_px", "why": f"nesne ekranda {metrics['object_px']} px (< {cfg['min_object_px']})"})
    metrics["cuts"] = _cuts(samples)
    if metrics["cuts"] > cfg["max_cuts"]:
        fails.append({"metric": "cuts", "why": f"aksiyon sürerken kamera {metrics['cuts']} kez kesiyor/sıçrıyor"})
    if not samples:
        fails.append({"metric": "samples", "why": "pencerede ölçülecek kare yok"})
    return {"beat": beat.get("i"), "shot": beat.get("shot_id"), "event": event["type"], "object": event["object"], "by": event.get("by"),
            "to": event.get("to"), "target": event.get("target"), "window": [round(a, 2), round(b, 2)], "metrics": metrics,
            "ok": not fails, "fails": fails}


def measure_plan(plan, designs, cfg=None):
    return [measure_event(plan, designs, beat, ev, cfg) for beat in plan.get("beats", []) for ev in action_events(beat)]


def problems(report):
    """Üretim kapısı biçimi: [{'rule','engine','shot','why'}]. Sorumlu motor: kamera (kadraj/kesme) ya da bloklama (örtme)."""
    out = []
    for r in report:
        for f in r["fails"]:
            engine = "camera" if f["metric"] in ("cuts", "object_px") else "staging"
            out.append({"rule": "ACTION_UNREADABLE", "engine": engine, "shot": r["shot"],
                        "why": f"{r['event']} {r['object']} ({r['by']}{' -> ' + r['to'] if r.get('to') else ''}{' => ' + r['target'] if r.get('target') else ''}): {f['why']}"})
    return out


__all__ = ["DEFAULTS", "action_events", "window", "sample", "measure_event", "measure_plan", "problems"]
