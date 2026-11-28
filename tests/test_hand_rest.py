"""Boşta ve yürürken eller gevşek (parmaklar aşağı, bitişik; belde 'dur' işareti gibi yukarı açılmaz); jest sırasında açık el korunur.
Ölçü pikselden: gerçek çizim yolunun el çağrıları boş tuvale yeniden çizilir; ten pikselinin el merkezinden yukarı / aşağı uzanışı ve
genişliği el yarıçapı cinsinden ölçülür. Yalnız sentetik değerler."""
import os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import shot_motion as sm  # noqa: E402

SKIN = (10, 200, 250)
CAST = {"child": (4, 0.98), "adult": (35, 1.9)}
REST_MAX_UP = 1.05          # gevşek el: ten merkezden yukarı en çok avuç kadar uzanır (el yarıçapı)
REST_MAX_WIDTH = 2.3
OPEN_MIN_UP = 1.25          # açık jest eli: parmaklar yukarı belirgin uzanır
EMOTIONS = ("neutral", "happy", "laugh", "surprise")


def design(name):
    age, h = CAST[name]
    d = pp.derive_design({"id": f"s_{name}", "age": age, "role": "erkek"}, {"height_m": h})
    d["skin"] = SKIN
    return d


def hands(des, pose, emo, monkeypatch, t=0.0):
    """{'L'|'R': (yukarı, aşağı, genişlik)} el yarıçapı cinsinden."""
    calls, real = {}, pp._hand

    def spy(cv, p, r, skin, sg, *a, **k):
        calls["L" if sg < 0 else "R"] = (p, r, skin, sg, a, k)

    with monkeypatch.context() as m:
        m.setattr(pp, "_hand", spy)
        pp.draw_character(pp.Cv(500, 600, ss=1), des, pose, {"mouth": "X", "blink": 0, "emotion": emo, "gaze": 0.0}, 250, 560, 220.0, t)
    out = {}
    for side, (p, r, skin, sg, a, k) in calls.items():
        r_ = 40.0
        cv = pp.Cv(300, 300, ss=1)
        real(cv, (150, 150), r_, skin, sg, a[0], 3.0, *a[2:], **k)
        px = cv.img.convert("RGB").load()
        pts = [(x, y) for y in range(300) for x in range(300) if px[x, y] == SKIN]
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        out[side] = ((150 - min(ys)) / r_, (max(ys) - 150) / r_, (max(xs) - min(xs)) / r_)
    return out


def relaxed(m):
    up, down, width = m
    return up <= REST_MAX_UP and down > up and width <= REST_MAX_WIDTH


def walk_poses(H, step=3):
    for x0, x1 in ((-1.0, 1.0), (1.2, -0.8)):
        for seed in range(4):
            for i in range(0, 97, step):
                p = sm.pose_at("walk", i / 24, 4.0, seed, x0, x1, H, 0.0)
                if pp.view_of(p) != "side":
                    yield (x0, seed, i), p


def bad_frames(des, poses, monkeypatch):
    bad, n = [], 0
    for key, p in poses:
        for emo in ("neutral", "happy"):
            for side, m in hands(des, p, emo, monkeypatch).items():
                n += 1
                if not relaxed(m):
                    bad.append((key, emo, side, m))
    return bad, n


@pytest.mark.parametrize("name", sorted(CAST))
def test_hands_are_relaxed_while_walking(name, monkeypatch):
    des = design(name)
    bad, n = bad_frames(des, walk_poses(des["height"], 6), monkeypatch)
    assert n > 100 and not bad, (len(bad), n, bad[:3])


@pytest.mark.parametrize("emo", EMOTIONS)
def test_resting_hands_are_relaxed_in_every_mood(emo, monkeypatch):
    p = pp._standing(0.0)
    p.update(head=[0.0, 0.0, 0.0], aL=[-0.1, 0.12], aR=[-0.1, -0.12], lL=0.0, lR=0.0)
    for side, m in hands(design("adult"), p, emo, monkeypatch, t=0.7).items():
        assert relaxed(m), (side, m)


@pytest.mark.parametrize("name", sorted(CAST))
def test_raised_gesture_hand_stays_open(name, monkeypatch):
    des = design(name)
    p = pp._standing(0.0)
    p.update(head=[0.0, 0.0, 0.0], aL=[0.0, 0.1], aR=[0.0, -2.2], lL=0.0, lR=0.0)      # sağ kol el sallar
    h = hands(des, p, "happy", monkeypatch)
    assert h["R"][0] >= OPEN_MIN_UP and relaxed(h["L"]), h


def test_reaching_hand_is_not_relaxed_and_the_change_is_gradual(monkeypatch):
    des = design("adult")
    base = pp._standing(0.0)
    base.update(head=[0.0, 0.0, 0.0], aL=[-0.1, 0.12], aR=[-0.1, -0.12], lL=0.0, lR=0.0)
    last = None
    for i in range(0, 41):
        p = dict(base, aL=list(base["aL"]), aR=list(base["aR"]))
        pp.arm_blend(des, p, "R", 0.25, 1.1, i / 40)
        w = pp.hand_rest(p, "R", p["aR"][1], p["aR"][0])
        if i == 0:
            assert w == 1.0 and "rwR" not in p
        if last is not None:
            assert 0.0 <= last - w <= 0.2, (i, last, w)             # biçim tek adımda değişmez
        last = w
    assert last == 0.0


def test_always_open_hands_are_caught(monkeypatch):
    """Bilerek eski davranış: gevşeklik yok; ölçü yakalar."""
    monkeypatch.setattr(pp, "hand_rest", lambda *a: 0.0)
    des = design("adult")
    bad, n = bad_frames(des, walk_poses(des["height"], 12), monkeypatch)
    assert len(bad) > n * 0.8, (len(bad), n)


def test_always_limp_hands_are_caught_in_a_gesture(monkeypatch):
    """Bilerek ters hata: jestte de gevşek el; ölçü yakalar."""
    monkeypatch.setattr(pp, "hand_rest", lambda *a: 1.0)
    p = pp._standing(0.0)
    p.update(head=[0.0, 0.0, 0.0], aL=[0.0, 0.1], aR=[0.0, -2.2], lL=0.0, lR=0.0)
    assert hands(design("adult"), p, "happy", monkeypatch)["R"][0] < OPEN_MIN_UP
