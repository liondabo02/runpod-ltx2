import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import puppet2d as pp, shot_motion as sm, turn_sheet as T
BIBLE = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile", "series-bible.json")
DES = T.design_set(BIBLE)

class Spy(pp.Cv):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.ell = []
    def ellipse(self, cx, cy, rx, ry, fill, ol=None, ow=3.0, rot=0.0, n=44):
        self.ell.append((cx, cy, rx, ry)); return super().ellipse(cx, cy, rx, ry, fill, ol, ow, rot, n)

def _drawn_hands(des, pose, ppm=300, fx=400, fy=700):
    cv = Spy(800, 760); pp.draw_character(cv, des, pose, {"mouth": "X"}, fx, fy, ppm, 0.3)
    Hh = des["height"] * ppm
    hs = [(c[0], c[1]) for c in cv.ell if abs(c[2] - Hh * 0.052 * 0.95) < 0.6 and abs(c[3] - Hh * 0.052 * 0.9) < 0.6]
    hs += [(c[0], c[1]) for c in cv.ell if abs(c[2] - Hh * 0.046) < 0.6 and abs(c[3] - Hh * 0.044) < 0.6]    # profil eli
    return hs, fx, fy, ppm

def test_hand_anchor_matches_drawn_hand_front_and_side():
    for cid in ("aden", "harun", "esra"):
        d = DES[cid]
        for view, yaw in (("front", 0.0), ("side", 1.0), ("side", -1.0)):
            for fwd, out in ((0.0, 0.1), (0.95, 0.30), (1.2, 0.1)):
                p = sm.base_pose(0.0); p["yaw"] = yaw; p["aL"] = [-fwd, 0.0 + out]; p["aR"] = [-fwd, -out]
                hs, fx, fy, ppm = _drawn_hands(d, p)
                assert hs, (cid, view)
                for side in "LR":
                    dx, h = pp.hand_offset(d, p, side)
                    ex, ey = fx + dx * ppm, fy - h * ppm
                    best = min(((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 for x, y in hs)
                    assert best < 3.0, (cid, view, side, fwd, out, best)        # çizilen el ile hesaplanan nokta ≤3px (ppm=300)
