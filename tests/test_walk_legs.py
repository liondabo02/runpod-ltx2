"""Ön / üç-çeyrek yürüyüşte iki bacak birbirinin içinden geçip X çizmez. Ölçü gerçek çizim yolundan: draw_character'ın bacak için
kullandığı noktalar (puppet2d.leg_lines) yakalanır. Yalnız sentetik değerler."""
import os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import shot_motion as sm  # noqa: E402

FPS = 24
ROUTES = [(-1.0, 1.0, 4.0), (1.2, -0.8, 4.0), (0.0, 0.5, 3.0), (-1.9, 1.9, 7.0)]
CLASSES = {"child": (4, 0.98), "adult": (35, 1.9)}


def design(cls):
    age, h = CLASSES[cls]
    return pp.derive_design({"id": f"s_{cls}", "age": age, "role": "erkek"}, {"height_m": h, "lowerwear": "pants"})


def _side(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def crossing(l, r, eps=1.0):
    """İki bacak doğru parçası birbirini iç noktada keser mi? Ortak kalça (ters V) kesişme sayılmaz."""
    (a, b), (c, d) = l, r
    if abs(a[0] - c[0]) < eps and abs(a[1] - c[1]) < eps:
        return False
    return _side(a, b, c) * _side(a, b, d) < -1e-6 and _side(c, d, a) * _side(c, d, b) < -1e-6


def drawn_legs(monkeypatch, des, poses):
    got, real = [], pp.leg_lines

    def spy(*a, **k):
        out = real(*a, **k); got.append(out); return out
    monkeypatch.setattr(pp, "leg_lines", spy)
    rows = []
    for p in poses:
        got.clear()
        cv = pp.Cv(400, 500, ss=1)
        pp.draw_character(cv, des, p, {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0}, 200, 470, 420 / des["height"], 0.0)
        if got:                                   # profil görünüş ayrı rig: bu ölçüye girmez
            rows.append(got[0])
    monkeypatch.setattr(pp, "leg_lines", real)
    return rows


def walk_poses(H, kind):
    for x0, x1, dur in ROUTES:
        for seed in range(4):
            yield [sm.pose_at(kind, i / FPS, dur, seed, x0, x1, H, 0.0) for i in range(int(dur * FPS) + 1)]


@pytest.mark.parametrize("kind", ["walk", "carry"])
@pytest.mark.parametrize("cls", sorted(CLASSES))
def test_walking_legs_never_cross_and_hips_do_not_jump(monkeypatch, cls, kind):
    des = design(cls)
    for poses in walk_poses(des["height"], kind):
        rows = drawn_legs(monkeypatch, des, poses)
        assert rows
        bad = [i for i, r in enumerate(rows) if crossing(r["L"], r["R"])]
        assert not bad, bad[:5]
        if len(rows) == len(poses):               # kesintisiz ön/üç-çeyrek dizi: kalça bir karede sıçramaz
            for side in "LR":
                step = max(abs((b[side][0][0]) - (a[side][0][0])) for a, b in zip(rows, rows[1:]))
                travel = max(abs(b["x"] - a["x"]) for a, b in zip(poses, poses[1:]))
                assert step <= 420 / des["height"] * travel + 420 * 0.03, (side, step)


@pytest.mark.parametrize("cls", sorted(CLASSES))
def test_standing_pose_keeps_the_hips_apart(monkeypatch, cls):
    des = design(cls)
    rows = drawn_legs(monkeypatch, des, [sm.base_pose(0.0)])
    assert rows[0]["R"][0][0] - rows[0]["L"][0][0] > 420 * 0.04, rows[0]


def test_fixed_hips_are_caught(monkeypatch):
    """Bilerek eski davranış: kalçalar adımdan bağımsız ayrık kalır; X yakalanır."""
    des = design("adult")
    real = pp.leg_lines

    def old(pose, fx, fy, Hh, leg_h, torso_h, torso_w, torso_bot, jump, sit):
        out = real(pose, fx, fy, Hh, leg_h, torso_h, torso_w, torso_bot, jump, sit)
        return {s: ((fx + sg * torso_w * pp.HIP_HALF_K, out[s][0][1]), out[s][1]) for s, sg in (("L", -1), ("R", 1))}
    monkeypatch.setattr(pp, "leg_lines", old)
    n = sum(crossing(r["L"], r["R"]) for poses in walk_poses(des["height"], "walk") for r in drawn_legs(monkeypatch, des, poses))
    assert n > 20, n
