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
