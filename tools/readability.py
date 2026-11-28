"""AHOS aksiyon okunabilirliği ölçüsü (genel motor; proje adı/koordinatı bilmez).
Her temas olayı (al / ver / bırak / çöpe at) penceresinde, renderer'ın GERÇEKTEN çizdiği katmanlardan (render2d.frame(trace=...))
piksel maskeleriyle şunlar ölçülür: nesne, temas eden el(ler), oyuncular ve atış/bırakma hedefi KADRAJDA ve ÖRTÜLMEMİŞ mi;
kamera bu pencerede başka yere kesiyor mu (aksiyon kadrajı süreklidir); nesne seçilebilecek kadar büyük mü.
Bu ölçü 'seyirci anladı' demek DEĞİLDİR: yalnız görünürlük/kadraj için gerekli koşulları denetler. Eşikler yapılandırılabilir ve insan izlemesiyle doğrulanmamıştır."""
import math

from PIL import Image, ImageChops, ImageDraw
import action_staging
import listener_reaction
import object_state
import pointing
import props2d
import puppet2d as pp
import scenes2d as sc
import setpieces2d
import render2d as r2
import shot_cuts

DEFAULTS = {
    "object_visible": 0.60,       # nesne piksellerinin kadrajda + örtülmemiş oranı (örnek başına)
    "hand_visible": 0.60,         # temas eden elin görünür oranı
    "actor_visible": 0.55,        # temasa katılan oyuncunun görünür oranı
    "target_visible": 0.60,       # hedef ağzının (atış/bırakma) görünür oranı
    "pass_ratio": 0.85,           # penceredeki örneklerin en az bu oranı her ölçütü sağlamalı
    "min_object_px": 14,          # nesnenin ekrandaki uzun kenarı (1280x720)
    "max_cuts": 0,                # pencere içinde kamera sıçraması sayısı
    # temassız anlarda oyuncular arası örtme (bloklama)
    "occl_visible": 0.60,         # oyuncunun kadrajdaki pikselinin en az bu oranı diğer oyunculardan açık
    "occl_head_visible": 0.90,    # baş bölgesinin (siluetin üst payı = baş boyu / boy) en az bu oranı açık: yüz asıl okunan yer
    "occl_max_s": 1.0,            # bundan uzun süren örtme sorun (yanından yürüyüp geçme gibi kısa kesişme serbest)
    "occl_fps": 4,
    # kazara alttan kesme (kadraj): ekran alt kenarı bacak ortasından ya da yakın planda konu nesnesinden geçemez
    "crop_fps": 4,
    "crop_leg_tol": 0.85,         # odakta olmayan oyuncuda alt kenar kalça yüksekliğinin en az bu katında olmalı (benzer boy payı); odakta kalçanın üstünde
    "crop_object_margin_px": 20,  # yakın planda odağın tuttuğu nesnenin alt kenarı ekran altından en az bu kadar yukarıda
    "close_tight_slack": 0.95,    # tam boy 'yakın' plan, o anın orta planından gerçek kesme eşiği x bu pay kadar dar olmalı (oyuncular çekim içinde yürür)
    # tepki planı: kamera dinleyene kesiyorsa o planda gerçekten tepki görünmeli
    "react_face_min": 0.015,      # planın ilerisindeki karede yüz, aynı pozun ifadesiz yüzünden baş kutusu piksellerinin en az bu oranında farklı
    "react_gaze_min": 0.5,        # göz bebeği konuşandan yana en az bu kadar kayık (nesne eylemi izleniyorsa aranmaz)
    "react_sample_at": 0.7,       # ölçülen kare: planın bu oranındaki an (ifade oturmuş olmalı)
    # kamera atlaması: kadraj tek karede değişiyor ama gerçek bir kesme kadar farklı değil
    "pop_zoom_step": 0.025,       # tek karede bundan büyük ölçek değişimi sürekli hareket sayılmaz
    "pop_jerk_px": 25,            # tek karelik kayma sıçraması: iki komşu karenin kaymasından bu kadar farklı (px, 1280x720)
    "cut_zoom_ratio": shot_cuts.CUT_ZOOM_RATIO,   # gerçek kesme: ölçek en az bu oranda değişir...
    "cut_shift_px": shot_cuts.CUT_SHIFT_PX,       # ...ya da merkez yatayda/dikeyde en az bu kadar kayar (kamera ile aynı kaynak)
    # gösterme jesti: jest boyunca hedef kadrajda ve açıkta, kol hedefe bakıyor
    "point_fps": 8,
    "point_target_visible": 0.60,  # gösterilen nesne/hedef piksellerinin kadrajda + örtülmemiş oranı
    "point_hand_visible": 0.75,    # gösteren el ve ön kol örnek noktalarının başka oyuncu/ön plan altında kalmayan oranı
    "point_angle_deg": 20.0,       # omuz->el doğrusu ile omuz->hedef doğrusu arasındaki en büyük açı
    "point_margin_px": 8,          # hedef merkezi ve gösterenin omzu/eli ekran kenarından en az bu kadar içeride
    "lead_s": 0.3, "tail_s": 0.3, "fps": 12,
    # kap içine atış (entry): nesne ağızdan, yukarıdan girip ağız çizgisinde parça parça kaybolmalı
    "entry_fps": 24,
    "entry_rim_tol_m": 0.06,      # son görünen karede nesnenin alt kenarı ağız çizgisine en çok bu kadar uzak
    "entry_side_tol_m": 0.04,     # son görünen karede nesne ağız açıklığının yanlarından en çok bu kadar taşabilir
    "entry_last_visible": 0.65,   # kaybolmadan önceki son karede nesnenin en çok bu oranı görünür (havada birden yok olmaz)
    "entry_max_step_m": 0.40,     # ardışık karede nesne merkezinin en büyük yolu (sıçrama)
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
        whole = getattr(fn, "full", fn)                             # kap ağzından içeri inerken katman kırpıktır; toplam alan kırpılmamış çizimden
        total = max(1, _count(_mask(whole, centred)))
        seen = _minus(masks[i], later(i, {(lay[0], lay[1]) for lay in layers if lay[0] == "grip"}))     # tutan parmaklar 'örtme' sayılmaz
        if whole is fn or _count(masks[i]) >= _count(_mask(whole, cam)):      # kırpma piksel aldıysa bu beklenen kayboluştur: onu 'entry' ölçütü denetler
            res["object"] = min(1.0, _count(seen) / total)
        bb = _mask(whole, centred).getbbox()
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


def _entry_frame(plan, designs, beat, event, lt):
    """Bir anda nesnenin çizilen görünümü: {'cam','vis' (görünen bbox|None),'frac' (görünen/toplam),'full' (kırpılmamış bbox|None)}."""
    tr = {}
    if r2.frame(plan, designs, beat["t_start"] + lt, trace=tr) is None:
        return None
    cam, layers = tr["cam"], tr["layers"]
    i = next((k for k, lay in enumerate(layers) if lay[0] == "object" and lay[1] == event["object"]), None)
    if i is None:
        return {"cam": cam, "vis": None, "frac": 0.0, "full": None}
    fn, at = layers[i][2], layers[i][3]
    whole = getattr(fn, "full", fn)
    total = max(1, _count(_mask(whole, sc.Cam(at[0], at[1], cam.z))))
    own = _mask(fn, cam)
    seen = _minus(own, _union([_mask(lay[2], cam) for lay in layers[i + 1:] if lay[0] != "grip"]))
    return {"cam": cam, "vis": seen.getbbox(), "frac": min(1.0, _count(seen) / total), "full": _mask(whole, cam).getbbox()}


def measure_entry(plan, designs, beat, event, cfg=None):
    """Kap içine atış, ÇİZİLEN karelerden (uçuş formülünden bağımsız): (ölçüm, sorun listesi). Koşullar:
    nesne ağız çizgisini yukarıdan ve açıklığın içinden geçer; ağız çizgisinin altında (kabın önünde) hiç çizilmez; son görünen karede ağız
    çizgisinde, açıklığın içinde ve büyük ölçüde içeri girmiştir; sonra bir daha görünmez; yolunda sıçrama yoktur."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    g = setpieces2d.mouth_of(event.get("target"))
    if not g:
        return {}, [f"hedefin ağız tanımı yok ({event.get('target')}): nesnenin içeri girdiği ölçülemez"]
    mx, rim, half = float(beat["targets"][event["target"]][0]), g["rim"], g["half"]
    dur = beat["t_end"] - beat["t_start"]
    a, b = event["t_start"], min(dur - 1e-3, event["t"] + cfg["tail_s"])
    n = max(2, int(round((b - a) * cfg["entry_fps"])) + 1)
    frames = [(lt, s) for lt in (a + (b - a) * k / (n - 1) for k in range(n)) for s in [_entry_frame(plan, designs, beat, event, lt)] if s]
    why, metrics = [], {}
    shown = [k for k, (_t, s) in enumerate(frames) if s["vis"]]
    if not shown:
        return metrics, ["uçuş boyunca nesne hiç görünmüyor"]
    last_t, last = frames[shown[-1]]
    cam = last["cam"]; px = cam.s
    x0, _y0, x1, y1 = last["vis"]
    metrics = {"last_seen_at": round(last_t, 3), "last_visible": round(last["frac"], 3),
               "last_bottom_above_rim_m": round((cam.y(rim) - y1) / px, 3),
               "last_side_overflow_m": round(max(cam.x(mx - half) - x0, x1 - cam.x(mx + half), 0.0) / px, 3)}
    if shown[-1] >= len(frames) - 1:
        why.append("nesne pencere sonunda hâlâ görünüyor (kabın içine girmiyor)")
    if abs(metrics["last_bottom_above_rim_m"]) > cfg["entry_rim_tol_m"]:
        why.append(f"nesne ağız çizgisinde kaybolmuyor: son görünüşte alt kenarı çizgiden {metrics['last_bottom_above_rim_m']:+.2f} m (+: havada kayboluyor, -: kabın önünde)")
    if metrics["last_side_overflow_m"] > cfg["entry_side_tol_m"]:
        why.append(f"nesne açıklığın dışında kayboluyor ({metrics['last_side_overflow_m']:.2f} m taşma): ıska")
    if last["frac"] > cfg["entry_last_visible"]:
        why.append(f"nesne içeri girmeden birden yok oluyor (son karede %{100 * last['frac']:.0f} görünür)")
    holes = [frames[k][0] for k in range(shown[0], shown[-1] + 1) if not frames[k][1]["vis"]]
    if holes:
        why.append(f"nesne uçuş ortasında kaybolup yeniden görünüyor ({holes[0]:.2f} sn)")
    below, step_max, prev = 0.0, 0.0, None
    crossed_ok = None
    for _t, s in frames:
        c = s["cam"]
        if s["vis"]:
            vx0, _a, vx1, vy1 = s["vis"]
            if vx1 > c.x(mx - half) and vx0 < c.x(mx + half):       # kabın üstündeki sütunda çizgi altına taşan çizim = kabın ÖNÜNDE
                below = max(below, (vy1 - c.y(rim)) / c.s)
        if s["full"]:
            fx0, fy0, fx1, fy1 = s["full"]
            wx = ((fx0 + fx1) / 2 - c.x(mx)) / c.s; wy = (c.y(rim) - (fy0 + fy1) / 2) / c.s      # ağıza göre merkez (m)
            if prev is not None:
                step_max = max(step_max, ((wx - prev[0]) ** 2 + (wy - prev[1]) ** 2) ** 0.5)
            bottom = (c.y(rim) - fy1) / c.s
            if crossed_ok is None and prev is not None and bottom <= 0.0 < prev[2] and abs(wx) <= half + 0.5:
                crossed_ok = abs(wx) <= half and abs(prev[0]) <= half + cfg["entry_max_step_m"] and wy < prev[1]
            prev = (wx, wy, bottom)
        else:
            prev = None
    metrics.update(below_rim_m=round(below, 3), max_step_m=round(step_max, 3), crossed_from_above=bool(crossed_ok))
    if below > cfg["entry_rim_tol_m"]:
        why.append(f"nesne ağız çizgisinin {below:.2f} m altında kabın önünde çiziliyor")
    if not crossed_ok:
        why.append("nesne ağız çizgisini yukarıdan ve açıklığın içinden geçmiyor")
    if step_max > cfg["entry_max_step_m"]:
        why.append(f"uçuşta sıçrama: ardışık karede {step_max:.2f} m")
    return metrics, why


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
    if event["type"] == "dispose":
        metrics["entry"], why = measure_entry(plan, designs, beat, event, cfg)
        fails.extend({"metric": "entry", "why": w} for w in why)
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
            engine = "camera" if f["metric"] in ("cuts", "object_px") else ("object_motion" if f["metric"] == "entry" else "staging")
            out.append({"rule": "ACTION_UNREADABLE", "engine": engine, "shot": r["shot"],
                        "why": f"{r['event']} {r['object']} ({r['by']}{' -> ' + r['to'] if r.get('to') else ''}{' => ' + r['target'] if r.get('target') else ''}): {f['why']}"})
    return out


def actor_cover(plan, designs, beat, lt):
    """Tek anda her çizilen oyuncunun diğer OYUNCULARDAN açık kalan payı: {kimlik: {'body': oran, 'head': oran, 'by': örten|None}}.
    Kadraj dışı pay sayılmaz."""
    tr = {}
    if r2.frame(plan, designs, beat["t_start"] + lt, trace=tr) is None:
        return {}
    cam = tr["cam"]
    people = [(key, _mask(fn, cam)) for kind, key, fn, _at in tr["layers"] if kind == "character"]
    out = {}
    for i, (cid, own) in enumerate(people):
        total = _count(own)
        if not total:
            continue
        over = people[i + 1:]
        if not over:
            out[cid] = {"body": 1.0, "head": 1.0, "by": None}
            continue
        seen = _minus(own, _union([m for _c, m in over]))
        x0, y0, x1, y1 = own.getbbox()
        d = designs[cid]
        top = cam.y(d["height"])                                  # baş payı oyuncunun boyundan: alttan kesilen kadrajda da aynı yer
        head = (0, 0, W, max(0, min(H, int(round(top + pp.head_share(d) * d["height"] * cam.s)))))
        h_all = _count(own.crop(head)) if head[3] else 0
        by = max(over, key=lambda cm: total - _count(_minus(own, cm[1])))[0]
        out[cid] = {"body": _count(seen) / total, "head": _count(seen.crop(head)) / h_all if h_all else 1.0, "by": by}
    return out


def measure_occlusion(plan, designs, cfg=None):
    """Temas penceresi DIŞINDA (temasta eller bilerek buluşur; orayı aksiyon ölçüsü denetler) bir oyuncunun diğerini uzun süre
    büyük ölçüde kapatması. Dönüş: [{'beat','shot','actor','by','from','to','seconds','worst'}] (yalnız süre sınırını aşanlar)."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    step = 1.0 / cfg["occl_fps"]
    out = []
    for beat in plan.get("beats", []):
        if len(beat.get("cast") or []) < 2:
            continue
        dur = beat["t_end"] - beat["t_start"]
        busy = [(a, b) for a, b, _e in action_staging.hold_windows(beat)]
        runs = {}

        def close(cid):
            r = runs.pop(cid, None)
            if r and r["n"] * step > cfg["occl_max_s"] + 1e-9:
                out.append({"beat": beat.get("i"), "shot": beat.get("shot_id"), "actor": cid, "by": r["by"],
                            "from": round(beat["t_start"] + r["a"], 2), "to": round(beat["t_start"] + r["b"], 2),
                            "seconds": round(r["n"] * step, 2), "body": round(r["body"], 3), "head": round(r["head"], 3)})
        for k in range(int(dur * cfg["occl_fps"])):
            lt = (k + 0.5) * step
            cover = {} if any(a <= lt <= b for a, b in busy) else actor_cover(plan, designs, beat, lt)
            hidden = {c: v for c, v in cover.items() if v["body"] < cfg["occl_visible"] or v["head"] < cfg["occl_head_visible"]}
            for cid in list(runs):
                if cid not in hidden:
                    close(cid)
            for cid, v in hidden.items():
                r = runs.setdefault(cid, {"a": lt, "b": lt, "n": 0, "body": 1.0, "head": 1.0, "by": v["by"]})
                r["b"] = lt; r["n"] += 1
                if min(v["body"], v["head"]) < min(r["body"], r["head"]):
                    r["by"] = v["by"]
                r["body"] = min(r["body"], v["body"]); r["head"] = min(r["head"], v["head"])
        for cid in list(runs):
            close(cid)
    return out


def occlusion_problems(report):
    """Üretim kapısı biçimi; sorumlu motor bloklama."""
    return [{"rule": "ACTOR_OCCLUDED", "engine": "staging", "shot": r["shot"],
             "why": f"{r['actor']} {r['from']:.2f}-{r['to']:.2f} sn arasında ({r['seconds']:.2f} sn) {r['by']} tarafından kapatılıyor (en kötü: gövde %{100 * r['body']:.0f}, baş %{100 * r['head']:.0f} görünür)"}
            for r in report]


def face_change(design, pose, state, cam):
    """Çizilen yüz, aynı pozda ve aynı kamerada ifadesiz çizilen yüzden ne kadar farklı? Dönüş: baş kutusundaki değişen piksel oranı (0..1)."""
    calm = dict(state, emotion="neutral", brow=0.0, blink=False, eyes_open=True)
    shown = dict(state, blink=False)                              # göz kırpma ifade sayılmaz
    masks = []
    for st in (shown, calm):
        cv = pp.Cv()
        pp.draw_character(cv, design, pose, st, cam.x(pose["x"]), cam.y(0.0), cam.s, 0.0)
        masks.append(cv.done().convert("RGB"))
    Hh = design["height"]
    chin = r2.head_chin_k(design)
    box = (max(0, int(cam.x(pose["x"] - 0.30 * Hh))), max(0, int(cam.y(Hh * r2.HEAD_TOP_K + pose.get("z", 0.0)))),
           min(W, int(cam.x(pose["x"] + 0.30 * Hh)) + 1), min(H, int(cam.y(Hh * chin + pose.get("z", 0.0))) + 1))
    if box[2] <= box[0] or box[3] <= box[1]:
        return 0.0
    r, g, b = ImageChops.difference(masks[0].crop(box), masks[1].crop(box)).split()
    diff = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > 28 else 0)
    return diff.histogram()[255] / float((box[2] - box[0]) * (box[3] - box[1]))


def reaction_shots(plan, designs, cfg=DEFAULTS):
    """Kameranın GERÇEKTEN dinleyene kestiği planlar (çizimle aynı kamera kararı) ve her birinin ölçümü:
    [{'shot','listener','speaker','t0','t1','seconds','cut_by_beat_end','face','gaze','watching','emotion'}]."""
    step = 1.0 / cfg["fps"]
    out = []
    for beat in plan.get("beats", []):
        for w in listener_reaction.camera_windows(beat, r2.action_blocks(beat)):
            seen = []
            k = int(math.ceil(w["t0"] / step - 1e-6))
            while k * step < min(w["t1"], beat["t_end"]) - 1e-9:
                tr = {}
                r2.frame(plan, designs, k * step, trace=tr, camera_only=True)
                if "close" in (tr.get("preset"), tr.get("opened_from")) and tr.get("focus") == w["listener"]:   # dürüstçe orta plana açılan tepki planı da ölçülür
                    seen.append(k * step)
                k += 1
            if not seen:
                continue
            at = seen[min(len(seen) - 1, int(len(seen) * cfg["react_sample_at"]))]
            tr = {}
            r2.frame(plan, designs, at, trace=tr)
            items = {i[0]: i for i in tr["items"]}
            who, spk = w["listener"], w["speaker"]
            st = tr["states"].get(who)
            row = {"shot": beat.get("shot_id") or str(beat.get("i")), "listener": who, "speaker": spk, "t0": round(seen[0], 3),
                   "t1": round(seen[-1] + step, 3), "seconds": round(len(seen) * step, 3), "sample_t": round(at, 3),
                   "cut_by_beat_end": seen[-1] + step >= beat["t_end"] - 1e-6, "face": 0.0, "gaze": 0.0, "watching": False, "emotion": None}
            if st is not None:                                          # None: dinleyen o karede hiç çizilmedi
                _c, d, p, *_ = items[who]
                toward = (1.0 if items[spk][2]["x"] > p["x"] else -1.0) if spk in items else 0.0
                row.update(face=round(face_change(d, p, st, tr["cam"]), 4), gaze=round(st["gaze"] * toward, 3),
                           watching=bool(st["watching"]), emotion=st["emotion"])
            out.append(row)
    return out


def reaction_problems(report, cfg=DEFAULTS):
    """Üretim kapısı biçimi: boş tepki planı (ifadesiz ya da konuşana bakmayan dinleyen) ve anlık kesme."""
    out = []
    for r in report:
        why = []
        if r["seconds"] < listener_reaction.MIN_SHOT_S - 1.0 / cfg["fps"] - 1e-6 and not r["cut_by_beat_end"]:
            why.append(("REACTION_FLASH", "camera", f"plan {r['seconds']:.2f} sn sürüyor (en az {listener_reaction.MIN_SHOT_S} sn)"))
        if r["face"] < cfg["react_face_min"]:
            why.append(("REACTION_NO_EXPRESSION", "acting", f"yüz ifadesizden yalnız %{100 * r['face']:.1f} farklı (en az %{100 * cfg['react_face_min']:.1f})"))
        if not r["watching"] and r["gaze"] < cfg["react_gaze_min"]:
            why.append(("REACTION_NOT_LOOKING", "acting", f"dinleyen konuşana bakmıyor (bakış ölçüsü {r['gaze']})"))
        out += [{"rule": rule, "engine": eng, "shot": r["shot"], "why": f"{r['listener']} tepki planı {r['t0']:.2f}-{r['t1']:.2f} sn: {text}"}
                for rule, eng, text in why]
    return out


def camera_pops(plan, designs, cfg=DEFAULTS):
    """Kare kare çizim kamerasından atlamalar: [{'t','shot','kind','from','to','zoom','dx','dy','walking'}].
    kind 'edit': aynı tür/aile ve aynı odakta kadraj atlıyor (kurgu ya da kamera hatası);
    kind 'framing': iki farklı kadraj kuralı (ör. aksiyon kadrajı <-> genel) birbirine çok yakın kesiyor.
    İkisi de üretimi durdurur: her kesme ya gerçek kesme eşiğini geçer ya da sürekli harekettir."""
    step = 1.0 / cfg["fps"]
    rows = []
    end = max((b["t_end"] for b in plan["beats"]), default=0.0)
    start = min((b["t_start"] for b in plan["beats"]), default=0.0)
    for i in range(int(round((end - start) / step))):
        tr = {}
        r2.frame(plan, designs, start + i * step, trace=tr, camera_only=True)
        rows.append((start + i * step, tr or None))
    moves = [None]
    for (_t0, a), (_t1, b) in zip(rows, rows[1:]):
        if a is None or b is None:
            moves.append(None)
            continue
        pc, c = a["cam"], b["cam"]
        moves.append((c.x(pc.cx) - W / 2, c.y(pc.cy) - H / 2, c.s / pc.s))
    out = []
    for i in range(1, len(rows)):
        if moves[i] is None:
            continue
        (t, b), a = rows[i], rows[i - 1][1]
        dx, dy, zr = moves[i]
        near = [m for m in (moves[i - 1] if i > 1 else None, moves[i + 1] if i + 1 < len(moves) else None) if m is not None]
        jerk = bool(near) and all(max(abs(dx - m[0]), abs(dy - m[1])) > cfg["pop_jerk_px"] for m in near)
        if abs(zr - 1.0) <= cfg["pop_zoom_step"] and not jerk:
            continue
        joined = a["beat"] is b["beat"] or shot_cuts.continues(a["beat"], b["beat"])
        if not joined:
            continue                                                # sahne/mekân/kadro değişimi: kadraj farkı küçük olsa da gerçek kesme
        # aynı yüzde süren yakın çekim vuruş sınırında tek karede ne kadar atlarsa atlasın kesme sayılmaz
        held_close = (a["beat"] is not b["beat"] and a["preset"] == b["preset"] and a["preset"] in r2.CLOSE_PRESETS and a["focus"] == b["focus"])
        if not held_close and (max(zr, 1.0 / zr) >= cfg["cut_zoom_ratio"] or abs(dx) >= cfg["cut_shift_px"][0] or abs(dy) >= cfg["cut_shift_px"][1]):
            continue                                                # gerçek kesme
        fa, fb = shot_cuts.family(a["preset"]), shot_cuts.family(b["preset"])
        same = fa == fb and (fa in ("group", "action", "point") or a["focus"] == b["focus"])
        beat = b["beat"]
        walking = sorted(c for c, m in beat["motion"].items() if r2.follow_steadiness(beat, designs, c, b["lt"]) < 0.5)
        out.append({"t": round(t, 3), "shot": beat.get("shot_id") or str(beat.get("i")), "kind": "edit" if same else "framing",
                    "from": a["preset"], "to": b["preset"], "zoom": round(zr, 3), "dx": round(dx, 1), "dy": round(dy, 1), "walking": walking})
    return out


def camera_pop_problems(report):
    return [{"engine": "camera", "rule": "CAMERA_JUMP", "shot": r["shot"],
             "why": f"{r['t']:.2f} sn kadraj tek karede atlıyor ({r['from']}->{r['to']}, ölçek x{r['zoom']}, kayma {r['dx']}/{r['dy']} px)"}
            for r in report]


def _point_sample(plan, designs, beat, item, lt, cfg):
    """Gösterme jestinin bir anı, ÇİZİLEN katmanlardan: {'preset','target_visible','target_inside','arm_inside','angle_deg'}."""
    tr = {}
    if r2.frame(plan, designs, beat["t_start"] + lt, trace=tr) is None:
        return None
    cam, layers = tr["cam"], tr["layers"]
    m_ = cfg["point_margin_px"]

    def inside(x, y):
        return m_ <= x <= W - m_ and m_ <= y <= H - m_
    by = item["by"]
    row = next((r for r in tr["items"] if r[0] == by), None)
    box = pointing.target_box(beat, designs, item, lt)
    drawn = any(k == "character" and key == by for k, key, _f, _a in layers)
    res = {"preset": tr["preset"], "target_visible": 0.0, "target_inside": False, "arm_inside": False, "angle_deg": 180.0, "hand_visible": 0.0}
    if row is None or box is None:
        return res
    _c, d, p, *_ = row
    tx, ty = box[0], (box[1] + box[2]) / 2
    res["target_inside"] = inside(cam.x(tx), cam.y(ty))
    side = pointing.arm_side(d, p, tx - p["x"])
    (sx, sh), (ex, eh), (hx, hh) = pp.arm_joints(d, p, side)
    ex = p["x"] + ex
    sx, hx, gx = p["x"] + sx, p["x"] + hx, tx - p["x"]
    res["arm_inside"] = drawn and inside(cam.x(sx), cam.y(sh)) and inside(cam.x(hx), cam.y(hh))
    ax, ay, bx, by_ = hx - sx, hh - sh, p["x"] + gx - sx, ty - sh
    res["angle_deg"] = abs(math.degrees(math.atan2(ax * by_ - ay * bx, ax * bx + ay * by_)))
    masks = [_mask(fn, cam) for _k, _key, fn, _at in layers]
    to = item.get("to")
    me = next((k for k, lay in enumerate(layers) if lay[0] == "character" and lay[1] == by), None)
    if me is not None:                                              # el + ön kolun dış yarısı: kolun nereye uzandığını okutan parça
        over = _union([masks[k] for k in range(me + 1, len(layers)) if layers[k][0] in ("character", "front") and layers[k][1] != by])
        seen_, all_ = 0.0, 0.0
        for u, rad in ((1.0, 1.0), (0.75, 0.7), (0.5, 0.7)):
            px_ = hx + (ex - hx) * (1.0 - u) * 2.0 if u < 1.0 else hx
            ph_ = hh + (eh - hh) * (1.0 - u) * 2.0 if u < 1.0 else hh
            disk, area = _disk(cam.x(px_), cam.y(ph_), max(3.0, pp.HAND_R_K * rad * d["height"] * cam.s))
            seen_ += _count(_minus(disk, over)); all_ += area
        res["hand_visible"] = min(1.0, seen_ / max(1.0, all_))

    def cover(i, skip=()):
        return _union([masks[j] for j in range(i + 1, len(layers)) if layers[j][0] not in ("grip",) + skip])
    i = None
    if isinstance(to, dict):
        ids = [ob.get("id") or ob.get("prop") for ob in (beat.get("choreo") or {}).get("objects", []) if ob.get("prop") == to.get("prop")]
        i = next((k for k, lay in enumerate(layers) if lay[0] == "object" and (lay[1] in ids or lay[1] == to.get("prop"))), None)
        if i is None:
            return res                                              # gösterilen nesne hiç çizilmiyor
    elif isinstance(to, str) and to in (beat.get("cast") or []):
        i = next((k for k, lay in enumerate(layers) if lay[0] == "character" and lay[1] == to), None)
        if i is None:
            return res
    if i is not None:
        fn, at = layers[i][2], layers[i][3]
        whole = getattr(fn, "full", fn)
        total = max(1, _count(_mask(whole, sc.Cam(at[0], at[1] if isinstance(to, dict) else (box[1] + box[2]) / 2, cam.z))))
        res["target_visible"] = min(1.0, _count(_minus(masks[i], cover(i))) / total)
    else:                                                           # adlı nokta: noktanın çevresi oyuncu/ön plan altında kalmıyor
        disk, area = _disk(cam.x(tx), cam.y(ty), 14.0)
        occ = _union([masks[k] for k in range(len(layers)) if layers[k][0] in ("character", "front")])
        res["target_visible"] = min(1.0, _count(_minus(disk, occ)) / area)
    return res


def measure_pointing(plan, designs, cfg=DEFAULTS):
    """Planın bütün gösterme jestleri: [{'shot','by','to','t0','t1','samples','ok': {ölçüt: oran},'worst': {...},'why': [..]}].
    Kolun tam uzandığı aralık (kalkış ve iniş hariç) ölçülür."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    out = []
    for beat in plan["beats"]:
        shot = beat.get("shot_id") or str(beat.get("i"))
        for item in pointing.items(beat):
            row = {"shot": shot, "by": item.get("by"), "to": item.get("to"), "samples": 0, "why": []}
            out.append(row)
            bad = pointing.problem(beat, item)
            if bad:
                row["why"].append({"rule": "JEST_COZULEMEDI", "why": f"{item.get('by')}: {bad}"})
                continue
            a, b = pointing.span(beat, item)
            row.update(t0=round(beat["t_start"] + a, 3), t1=round(beat["t_start"] + b, 3))
            a, b = a + pointing.RAMP_S, min(b - pointing.RAMP_S, beat["t_end"] - beat["t_start"] - 1e-3)
            n = max(2, int(round((b - a) * cfg["point_fps"])) + 1)
            seen = [s for s in (_point_sample(plan, designs, beat, item, a + (b - a) * k / (n - 1), cfg) for k in range(n)) if s]
            row["samples"] = len(seen)
            checks = {"target": [s["target_inside"] and s["target_visible"] >= cfg["point_target_visible"] for s in seen],
                      "arm_inside": [s["arm_inside"] for s in seen],
                      "arm_aim": [s["angle_deg"] <= cfg["point_angle_deg"] for s in seen],
                      "hand": [s["hand_visible"] >= cfg["point_hand_visible"] for s in seen]}
            row["ok"] = {k: round(sum(v) / max(1, len(v)), 3) for k, v in checks.items()}
            row["worst"] = {"target_visible": round(min((s["target_visible"] for s in seen), default=0.0), 3),
                            "angle_deg": round(max((s["angle_deg"] for s in seen), default=180.0), 1),
                            "hand_visible": round(min((s["hand_visible"] for s in seen), default=0.0), 3)}
            for key, rule, text in (("target", "JEST_HEDEFI_GORUNMUYOR", "gösterilen hedef jest boyunca kadrajda/açıkta değil"),
                                    ("arm_inside", "JEST_OYUNCU_KADRAJ_DISI", "gösteren kol kadrajda değil"),
                                    ("arm_aim", "JEST_KOLU_HEDEFE_BAKMIYOR", "gösteren kol hedefe bakmıyor"),
                                    ("hand", "JEST_KOLU_ORTULU", "gösteren el başka bir oyuncunun/ön planın arkasında")):
                if row["ok"][key] < cfg["pass_ratio"]:
                    row["why"].append({"rule": rule, "why": f"{item['by']}: {row['t0']:.2f}-{row['t1']:.2f} sn {text} (örneklerin yalnız %{100 * row['ok'][key]:.0f}'i; "
                                                          f"en kötü hedef görünürlüğü {row['worst']['target_visible']}, el görünürlüğü {row['worst']['hand_visible']}, açı {row['worst']['angle_deg']} derece)"})
    return out


def pointing_problems(report):
    return [{"engine": "camera", "rule": w["rule"], "shot": r["shot"], "why": w["why"]} for r in report for w in r["why"]]


__all__ = ["measure_pointing", "pointing_problems", "camera_pops", "camera_pop_problems", "face_change", "reaction_shots", "reaction_problems", "DEFAULTS", "action_events", "window", "sample", "measure_event", "measure_plan", "problems",
           "actor_cover", "measure_occlusion", "occlusion_problems"]


def crop_frame(plan, designs, t, cfg=DEFAULTS):
    """t anında kamera kararından (çizimle aynı kod yolu) alttan kesme ihlalleri ve kasıtlı üst beden kesmesi bilgisi: (ihlaller, kip) ya da None."""
    tr = {}
    r2.frame(plan, designs, t, trace=tr, camera_only=True)
    if not tr:
        return None
    cam, beat, lt = tr["cam"], tr["beat"], tr["lt"]
    bottom, ground = r2.frame_bottom(cam), cam.y(0.0)
    close = tr["preset"] in ("close", "xclose")
    out = []
    if close and tr.get("crop") == "full" and tr.get("soft") is None:     # 'yakın' denen plan tam boya açılmışsa grup planından gerçek kesme kadar dar olmalı
        group = r2.group_framing(beat, designs, [i[2]["x"] for i in tr["items"]], "medium", 0.0)[2]
        ratio = cam.z / group
        if ratio < shot_cuts.CUT_ZOOM_RATIO * cfg["close_tight_slack"]:
            hh = designs[tr["focus"]]["height"] * cam.s / H
            out.append({"rule": "YAKIN_PLAN_YAKIN_DEGIL", "who": tr["focus"], "tightness": round(ratio, 3), "height_over_frame": round(hh, 2)})
    if ground > r2.FEET_MAX_PX + 0.5:
        for cid, d, p, *_ in tr["items"]:
            if cid not in tr["drawn"] or not 0 <= cam.x(p["x"]) <= W:
                continue
            focus = close and cid == tr["focus"]
            need = r2.hip_height(d) * (1.0 if focus else cfg["crop_leg_tol"])
            if bottom < need - 1e-6:
                out.append({"rule": "ALTTAN_KAZARA_KESIK", "who": cid, "cut_m": round(bottom, 3), "hip_m": round(r2.hip_height(d), 3)})
    if close and (beat.get("choreo") or {}).get("objects"):
        for ob, x, y, _st, own, _h in r2._objects_now(beat, tr["items"], lt, tr["items_at"]):
            if own is None or own != tr["focus"]:
                continue
            low_px = cam.y(y - props2d.extent(ob.get("prop", ""), ob.get("scale", 0.55))[0])
            if low_px > H - cfg["crop_object_margin_px"] + 0.5:
                out.append({"rule": "KONU_NESNE_ALTTAN_KESIK", "who": own, "prop": ob.get("prop"), "bottom_px": round(low_px, 1)})
    return out, tr.get("crop"), tr["preset"]


def measure_crop(plan, designs, cfg=DEFAULTS):
    """Bütün plan: {'violations': [...birleştirilmiş zaman aralıkları], 'intentional': [kasıtlı üst beden kesmesi aralıkları]}."""
    step = 1.0 / cfg["crop_fps"]
    bad, upper = {}, {}

    def extend(store, key, t, row):
        spans = store.setdefault(key, [])
        if spans and t - spans[-1]["t1"] <= step + 1e-6:
            spans[-1]["t1"] = round(t, 3)
        else:
            spans.append(dict(row, t0=round(t, 3), t1=round(t, 3)))
    for beat in plan["beats"]:
        for i in range(int(round((beat["t_end"] - beat["t_start"]) * cfg["crop_fps"]))):
            t = beat["t_start"] + i * step
            res = crop_frame(plan, designs, t, cfg)
            if res is None:
                continue
            shot = beat.get("shot_id") or str(beat.get("i"))
            for v in res[0]:
                extend(bad, (shot, v["rule"], v["who"]), t, dict(v, shot=shot))
            if res[1] == "upper":
                extend(upper, shot, t, {"shot": shot, "preset": res[2], "crop": "upper_intentional"})
    return {"violations": [s for v in bad.values() for s in v], "intentional": [s for v in upper.values() for s in v]}


def crop_problems(report):
    return [{"engine": "camera", "rule": v["rule"], "shot": v["shot"],
             "why": f"{v['who']}: {v['t0']:.2f}-{v['t1']:.2f} sn " + (f"alt kadraj kenarı bacak ortasından geçiyor ({v['cut_m']} m, kalça {v['hip_m']} m)" if v["rule"] == "ALTTAN_KAZARA_KESIK"
                    else f"'yakın' plan tam boya açık: orta plandan yalnız x{v['tightness']} dar (boy/kare {v['height_over_frame']})" if v["rule"] == "YAKIN_PLAN_YAKIN_DEGIL"
                    else f"alt kadraj kenarı tutulan '{v.get('prop')}' nesnesini kesiyor")}
            for v in report["violations"]]
