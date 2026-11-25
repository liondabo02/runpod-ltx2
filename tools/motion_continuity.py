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
