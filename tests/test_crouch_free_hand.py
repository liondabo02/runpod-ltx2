"""Çömelerek devirde boştaki el ayakkabının üstüne inmez (H25). Ölçü çizim geometrisinden: el dairesi (elin gerçek konumu ve
yarıçapı) çizilen ayakkabı elipslerine binmez. Tamamen sentetik projeler (test_kneel_handoff düzeni)."""
import math

import pytest

import test_kneel_handoff as kh
import puppet2d as pp
import readability as rd
import render2d as r2


def shoes(des, pose, monkeypatch):
    """Çizilen ayakkabı elipsleri, ayağa göre metre: (dx, yükseklik, rx, ry)."""
    ppm, fx, fy = 200.0, 640.0, 650.0
    found, real = [], pp.Cv.ellipse
    colour = pp.shade(des["accent"], 0.9)

    def spy(self, cx, cy, rx, ry, fill, *a, **k):
        if tuple(fill) == tuple(colour):
            found.append(((cx - fx) / ppm, (fy - cy) / ppm, rx / ppm, ry / ppm))
        real(self, cx, cy, rx, ry, fill, *a, **k)

    with monkeypatch.context() as m:
        m.setattr(pp.Cv, "ellipse", spy)
        pp.draw_character(pp.Cv(1280, 720, 1), des, pose, {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0}, fx, fy, ppm, 0.0)
    assert len(found) >= 2, found
    return found[:2]


def overlaps(des, pose, side, monkeypatch):
    hx, hh = pp.hand_offset(des, pose, side)
    edge = 0.0095 * des["height"]                           # dış çizginin yarısı (boyun 0,019'u): karede görünen sınır
    r = pp.HAND_R_K * des["height"] + edge
    pts = [(hx + r * q * math.cos(a / 24 * 2 * math.pi), hh + r * q * math.sin(a / 24 * 2 * math.pi)) for a in range(24) for q in (0.5, 1.0)]
    return any(((x - sx) / (rx + edge)) ** 2 + ((y - sy) / (ry + edge)) ** 2 < 1.0 for sx, sy, rx, ry in shoes(des, pose, monkeypatch) for x, y in pts)


def crouch_frames(plan, des):
    """Derin çömelme anları: (t, tasarım, poz)."""
    end = plan["beats"][-1]["t_end"]
    for k in range(int(end * 12)):
        for item in r2.poses_at(plan, des, k / 12):
            d, p = item[1], item[2]
            if pp.crouch_of(d, p) > 0.5 * pp.CROUCH_MAX_K * d["height"] * pp.LEG_K[d["class"]] and pp.view_of(p) != "side":
                yield k / 12, d, p


def found(tmp_path, name, monkeypatch):
    plan, des = kh.project(tmp_path, name)
    frames = list(crouch_frames(plan, des))
    return frames, [(round(t, 2), s) for t, d, p in frames for s in "LR" if overlaps(d, p, s, monkeypatch)]


DEEP = ("cocuk_buyuge_saga", "buyuk_cocuga_sola")


@pytest.mark.parametrize("name", DEEP)
def test_free_hand_stays_off_the_shoes_while_crouched(tmp_path, name, monkeypatch):
    frames, bad = found(tmp_path, name, monkeypatch)
    assert frames, "sahnede derin çömelme yok"
    assert not bad, bad[:10]


@pytest.mark.parametrize("name", DEEP)
def test_lifting_the_hand_adds_no_pose_or_object_jump(tmp_path, name):
    plan, des = kh.project(tmp_path, name)
    assert not rd.pose_jumps(plan, des)
    assert not rd.object_jumps(plan, des)


def test_old_hanging_arm_is_caught(tmp_path, monkeypatch):
    """Bilerek eski davranış: el sarktığı yerde kalır ve ayakkabıya biner."""
    monkeypatch.setattr(pp, "keep_hand_off_feet", lambda des, pose, side, w: None)
    bad = []
    for i, name in enumerate(DEEP):
        bad += found(tmp_path / str(i), name, monkeypatch)[1]
    assert bad


def test_a_raised_arm_is_not_touched():
    des = kh.design(1.9, 40)
    pose = dict(pp._standing(0.0), crouch=0.4, aL=[0.0, 2.0], aR=[0.0, -2.0], head=[0.0, 0.0, 0.0], lL=0.0, lR=0.0)
    before = [pp.hand_offset(des, pose, s) for s in "LR"]
    for s in "LR":
        pp.keep_hand_off_feet(des, pose, s, 1.0)
    assert [pp.hand_offset(des, pose, s) for s in "LR"] == before
