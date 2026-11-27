"""Hareket süreklilik ölçüsü: kare-kare poz sıçraması (ani poz atlaması) ve evre varlığı. Otomatik ölçer; oyunculuğun iyi olduğunu KANITLAMAZ."""
import math

def _flat(p):
    return {"yaw": p["yaw"], "lean": p["lean"], "sq": p.get("sq", 1.0), "z": p["z"],
            "h0": p["head"][0], "h2": p["head"][2], "aL0": p["aL"][0], "aR0": p["aR"][0], "aL1": p["aL"][1], "aR1": p["aR"][1]}

def jumps(sm, kind, H, dur=3.0, x0=-1.0, x1=1.0, fps=24, seed=0):
    prev = None; worst = {}; arg = {}
    for i in range(int(dur * fps) + 1):
        t = i / fps
        f = _flat(sm.pose_at(kind, t, dur, seed, x0, x1, H, 0.5 * H))
        if prev:
            for k in f:
                d = abs(f[k] - prev[k])
                if d > worst.get(k, 0): worst[k] = d; arg[k] = round(t, 3)
        prev = f
    return worst, arg

def phase_signature(sm, kind, H, dur=3.0, x0=-1.0, x1=1.0, seed=0, fps=24):
    """Hazırlık: harekete başlamadan önce gövde geri yaslanır; toparlanma: durduktan sonra ileri aşma var mı."""
    mn0 = min(sm.pose_at(kind, i / fps, dur, seed, x0, x1, H, 0.5 * H)["lean"] for i in range(int(0.5 * fps)))
    pm = sm.pose_at(kind, dur * 0.5, dur, seed, x0, x1, H, 0.5 * H)
    mn_end = min(sm.pose_at(kind, dur * 0.85 + i / fps, dur, seed, x0, x1, H, 0.5 * H)["lean"] for i in range(int(0.3 * dur * fps)))
    return {"anticipation": mn0 < pm["lean"] - 0.01, "recovery_overshoot": mn_end < pm["lean"] - 0.01}


# ---------------------------------------------------------------- yürüyüş başı/sonu duruşu
STANCE_LIMITS = {
    "rest_tol": 0.005,        # H: gövde dururken ayağın duruş yerinden en büyük sapması (ve yerden yüksekliği)
    "edge_step": 0.035,       # H: gövdenin neredeyse durduğu karelerde (başlangıç/varış) ayağın GÖVDEYE göre tek karedeki en büyük değişimi
    "still_body": 0.004,      # H/kare: gövde bundan yavaşsa 'neredeyse duruyor'
    "end_s": 0.25,            # sn: dizinin son bu kadarı 'varıştan sonra' sayılır
}


def foot_row(pose):
    """Pozdan (gövde_x, sol_ofset, sol_yükseklik, sağ_ofset, sağ_yükseklik); adım anahtarı yoksa ayaklar duruş yerindedir (çizimle aynı kural)."""
    return (pose["x"], pose.get("fL", 0.0), pose.get("hL", 0.0), pose.get("fR", 0.0), pose.get("hR", 0.0))


def stance_report(rows, H, limits=None):
    """rows: ardışık karelerin foot_row listesi (yürüyüş öncesinden varış sonrasına). Dönüş: (ölçüm, sorun listesi).
    Denetlenen: yürüyüş duruş pozundan başlar; varınca iki ayak duruş yerinde ve yerdedir; gövde neredeyse dururken bacaklar tek karede sıçramaz."""
    L = dict(STANCE_LIMITS, **(limits or {}))
    if len(rows) < 3:
        return {}, ["ölçülecek kare yok"]
    n_end = max(1, min(len(rows) - 1, int(round(L["end_s"] * L.get("fps", 24)))))
    off = lambda r: max(abs(r[1]), abs(r[3]))
    lift = lambda r: max(r[2], r[4])
    end = rows[-n_end:]
    m = {"start_offset": off(rows[0]), "end_offset": max(off(r) for r in end), "end_lift": max(lift(r) for r in end), "edge_step": 0.0}
    for a, b in zip(rows, rows[1:]):
        if abs(b[0] - a[0]) / H <= L["still_body"]:
            m["edge_step"] = max(m["edge_step"], abs(b[1] - a[1]), abs(b[3] - a[3]))
    why = []
    if m["start_offset"] > L["rest_tol"]:
        why.append(f"yürüyüş bacaklar ayrık başlıyor ({m['start_offset']:.3f} H)")
    if m["end_offset"] > L["rest_tol"]:
        why.append(f"varıştan sonra bacaklar ayrık ({m['end_offset']:.3f} H)")
    if m["end_lift"] > L["rest_tol"]:
        why.append(f"varıştan sonra ayak havada ({m['end_lift']:.3f} H)")
    if m["edge_step"] > L["edge_step"]:
        why.append(f"gövde dururken bacak tek karede sıçrıyor ({m['edge_step']:.3f} H)")
    return {k: round(v, 4) for k, v in m.items()}, why


# ---------------------------------------------------------------- ayak tozu: ÇİZİLEN karelerden ölçü (toz formülünü bilmez)
DUST_LIMITS = {
    "still_speed": 0.02,      # boy/sn: son 'still_win' süresinde gövde bundan yavaşsa 'duruyor' -> toz pikseli olmamalı
    "still_win": 1.0 / 12,
    "still_px": 4,            # kenar yumuşatma payı (piksel)
    "target_px": 4,           # dekor/hedef parçasının İÇİNE düşen toz pikseli payı
    "trail_walk": 1.0,        # boy: toz gövde merkezinden en çok bu kadar geride (yürüyüş)
    "trail_run": 1.7,         # boy: koşu (hız çizgileri dahil)
    "start_back": 0.40,       # boy: yürüyüşün başladığı yerin en çok bu kadar gerisinde (topuk + yarıçap payı)
    "ahead": 0.35,            # boy: gövde merkezinin en çok bu kadar önünde
}


def sample_dust(plan, designs, cid, times, still_win=DUST_LIMITS["still_win"]):
    """Her an için iki kare çizilir (toz açık / kapalı); fark = ekrana GERÇEKTEN gelen toz. Yalnız ölçülen oyuncu yürürken kullanın.
    Dönüş satırları: {'t','speed' (boy/sn),'px','target_px' (dekor parçasının içine düşen),'behind','ahead','before_start' (boy),'run'}."""
    from PIL import ImageChops, ImageFilter
    import fx_layer, readability, render2d, setpieces2d, shot_motion as sm
    H = designs[cid]["height"]
    rows = []
    for t in times:
        beat = next(b for b in plan["beats"] if b["t_start"] <= t < b["t_end"])
        lt, dur, m = t - beat["t_start"], beat["t_end"] - beat["t_start"], beat["motion"][cid]
        trace = {}
        on = render2d.frame(plan, designs, t, trace=trace)
        real = fx_layer.dust
        fx_layer.dust = lambda *a, **k: None
        try:
            off = render2d.frame(plan, designs, t)
        finally:
            fx_layer.dust = real
        mask = ImageChops.difference(on, off).convert("L").point(lambda v: 255 if v > 8 else 0)
        x = sm.motion_x(m, lt, dur, H)
        back = max(0.0, lt - still_win)
        speed = abs(x - sm.motion_x(m, back, dur, H)) / max(1e-6, lt - back) / H if lt > back else 0.0
        seg = sm.segment(m, lt, dur)[0]
        row = {"t": round(t, 4), "speed": speed, "px": mask.histogram()[255], "target_px": 0,
               "behind": 0.0, "ahead": 0.0, "before_start": 0.0, "run": seg["kind"] == "run"}
        if row["px"]:
            cam = trace["cam"]
            pieces = readability._mask(lambda cv, cm: setpieces2d.draw(cv, cm, beat.get("loc"), t, pieces=beat.get("pieces")), cam)
            inner = pieces.filter(ImageFilter.MinFilter(5))                 # kenar yumuşatma pikselleri sayılmaz
            row["target_px"] = ImageChops.darker(mask, inner).histogram()[255]
            x0px, _y0, x1px, _y1 = mask.getbbox()
            lo, hi = (cam.cx + (v - cam.x(cam.cx)) / cam.s for v in (x0px, x1px))
            d = 1.0 if seg["x1"] >= seg["x0"] else -1.0
            rear, front = (lo, hi) if d > 0 else (hi, lo)
            row["behind"] = max(0.0, d * (x - rear)) / H
            row["ahead"] = max(0.0, d * (front - x)) / H
            row["before_start"] = max(0.0, d * (seg["x0"] - rear)) / H
        rows.append(row)
    return rows


def dust_report(rows, limits=None):
    """sample_dust satırlarından (ölçüm, sorun listesi): duran gövdede toz yok; toz hedef/dekorun önünü örtmez; yürünen yolun yakınında kalır."""
    L = dict(DUST_LIMITS, **(limits or {}))
    still = [r for r in rows if r["speed"] <= L["still_speed"]]
    m = {"frames": len(rows), "dusty_frames": sum(1 for r in rows if r["px"] > L["still_px"]),
         "still_dust_px": max((r["px"] for r in still), default=0), "target_dust_px": max((r["target_px"] for r in rows), default=0),
         "max_behind": max((r["behind"] for r in rows), default=0.0), "max_ahead": max((r["ahead"] for r in rows), default=0.0),
         "max_before_start": max((r["before_start"] for r in rows), default=0.0)}
    why = []
    if m["still_dust_px"] > L["still_px"]:
        bad = next(r for r in still if r["px"] > L["still_px"])
        why.append(f"gövde dururken toz çiziliyor ({bad['t']:.2f} sn, {bad['px']} px)")
    if m["target_dust_px"] > L["target_px"]:
        why.append(f"toz dekor/hedef parçasının önünü örtüyor ({m['target_dust_px']} px)")
    far = [r for r in rows if r["behind"] > L["trail_run" if r["run"] else "trail_walk"]]
    if far:
        why.append(f"toz gövdeden çok geride ({max(r['behind'] for r in far):.2f} boy)")
    if m["max_before_start"] > L["start_back"]:
        why.append(f"toz hiç yürünmeyen yerde ({m['max_before_start']:.2f} boy, başlangıcın gerisinde)")
    if m["max_ahead"] > L["ahead"]:
        why.append(f"toz oyuncunun önünde ({m['max_ahead']:.2f} boy)")
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}, why
