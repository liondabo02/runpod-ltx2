"""Ayak kayması ölçümü. Temas eden ayağın DÜNYA koordinatındaki hızını ölçer (kamera hareketi hesaba girmez: kamera piksel
dönüşümüdür, dünya koordinatını değiştirmez). Birim: karakter boyu/saniye (H/s) — keyfî piksel sınırı yok.
Temas: ayağın kalkma yüksekliği ~0. Kabul eşiği SLIDE_LIMIT karakter boyunun saniyede %SLIDE_LIMIT*100'ü."""
import importlib.util, math, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
SLIDE_LIMIT = 0.06          # H/s: yürüyüşte temas ayağı en çok boyun %6'sı/sn kayabilir (gözle fark edilmeyen düzey)

def _load(path, name):
    sys.path.insert(0, HERE)
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

def world_feet(sm, kind, H, x0=-1.0, x1=1.0, dur=3.0, fps=24, seed=1, legacy=False):
    """Her kare için (sol_x, sol_temas, sağ_x, sağ_temas, t, gövde_x) — m."""
    rows = []
    n = int(dur * fps)
    for i in range(n):
        t = i / fps
        p = sm.pose_at(kind, t, dur, seed, x0, x1, H, 0.0)
        out = [t, p["x"]]
        for side, sg in (("L", -1), ("R", 1)):
            if not legacy and ("f" + side) in p:
                fx = p["x"] + p["f" + side] * H; contact = p["h" + side] < 1e-9
            else:
                cls_leg = 0.28 if H < 1.25 else 0.38                       # eski motor: ayak ofseti = swing*leg_h*0.066*sg, temas swing<=0
                swing = p["lL"] if side == "L" else p["lR"]
                fx = p["x"] + swing * cls_leg * H * 0.22 * sg * 0.3; contact = swing <= 0
            out += [fx, contact]
        rows.append(out)
    return rows

def slide_stats(rows, H, fps=24, inject=0.0):
    """Ardışık temas karelerinde aynı ayağın dünya hızı (H/s). inject: bilerek eklenen kayma (H/s) — test için."""
    res = []
    for ci, (xi, ki) in enumerate(((2, 3), (4, 5))):
        for a, b in zip(rows, rows[1:]):
            if a[ki] and b[ki]:
                dx = (b[xi] - a[xi]) + inject * H / fps
                res.append(abs(dx) * fps / H)
    res.sort()
    if not res: return {"n": 0, "p95": 0.0, "max": 0.0}
    return {"n": len(res), "p95": res[int(0.95 * (len(res) - 1))], "max": res[-1]}

def check(sm, kind="walk", H=1.7, inject=0.0, legacy=False, **kw):
    r = world_feet(sm, kind, H, legacy=legacy, **kw)
    s = slide_stats(r, H, inject=inject)
    s["pass"] = s["n"] > 0 and s["p95"] <= SLIDE_LIMIT
    return s

if __name__ == "__main__":
    new = _load(os.path.join(HERE, "shot_motion.py"), "sm_new")
    for kind in ("walk", "run"):
        for H in (1.0, 1.7):
            print("YENİ ", kind, H, check(new, kind, H))
    if len(sys.argv) > 1:
        old = _load(sys.argv[1], "sm_old")
        for H in (1.0, 1.7): print("ESKİ ", "walk", H, check(old, "walk", H, legacy=True))
