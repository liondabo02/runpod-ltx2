"""Yüz yana dönükken göz (uzak göz dahil) baş dış çizgisinin içinde kalır (H23). Ölçü çizim çağrılarından: göz akı elipsinin
her noktası baş elipsinin içinde ve dış çizgiden en az bir çizgi payı geride. Yalnız sentetik değerler."""
import math, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402

WHITE = (255, 255, 255)
CAST = {"bebek": (1, 0.75), "cocuk": (6, 0.98), "yetiskin": (35, 1.9), "yasli": (70, 1.65)}
SHAPES = ("round", "almond", "wide", "narrow", "sleepy")
YAWS = (-0.75, -0.6, -0.45, 0.0, 0.45, 0.6, 0.75)
TURNS = (-1.0, -0.5, 0.0, 0.5, 1.0)                 # baş dönüşü (bakılan kişi / dinleme)


def design(name, **over):
    age, h = CAST[name]
    des = pp.derive_design({"id": f"s_{name}", "age": age, "role": "erkek"}, {"height_m": h})
    des.update(over)
    return des


def draw(des, yaw, turn, emo, monkeypatch):
    """(baş elipsi (cx, cy, rx, ry), [göz akı elipsleri soldan sağa], dış çizgi kalınlığı)."""
    p = pp._standing(0.0)
    p.update(head=[0.0, 0.0, turn], aL=[0.0, 0.1], aR=[0.0, -0.1], lL=0.0, lR=0.0, yaw=yaw, view="three_quarter" if yaw else "front")
    heads, eyes, real_cel, real = [], [], pp.Cv.ellipse_cel, pp.Cv.ellipse

    def spy_cel(self, cx, cy, rx, ry, fill, *a, **k):
        if tuple(fill) == tuple(des["skin"]):
            heads.append((cx, cy, rx, ry))
        real_cel(self, cx, cy, rx, ry, fill, *a, **k)

    def spy(self, cx, cy, rx, ry, fill, *a, **k):
        if fill == WHITE and rx > 8 and abs(rx - ry) > 1e-6:      # parıltı noktası daire
            eyes.append((cx, cy, rx, ry))
        real(self, cx, cy, rx, ry, fill, *a, **k)

    with monkeypatch.context() as m:
        m.setattr(pp.Cv, "ellipse_cel", spy_cel)
        m.setattr(pp.Cv, "ellipse", spy)
        pp.draw_character(pp.Cv(600, 700, ss=1), des, p, {"mouth": "X", "blink": 0, "emotion": emo, "gaze": 0.0}, 300, 660, 560.0 / des["height"], 0.0)
    assert len(eyes) == 2 and heads, (heads, eyes)
    Hh = des["height"] * (560.0 / des["height"])
    return heads[-1], sorted(eyes), max(3.0, Hh * 0.019)


def worst_outside(head, eye):
    """Göz akının baş elipsinden dışarı en çok taşan noktası, yatayda px (eksi: içeride kalan pay)."""
    hx, hy, hr, hry = head
    cx, cy, rx, ry = eye
    worst = -1e9
    for i in range(72):
        a = 2 * math.pi * i / 72
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        half = hr * math.sqrt(max(0.0, 1.0 - ((y - hy) / hry) ** 2))
        worst = max(worst, abs(x - hx) - half)
    return worst


def sweep(name, monkeypatch, shapes=SHAPES):
    bad, gaps = [], []
    for shape in shapes:
        for emo in ("neutral", "surprise", "sad"):          # gülen göz aynı merkez ve yarıçaptan kesilir
            for yaw in YAWS:
                for turn in TURNS:
                    head, eyes, ow = draw(design(name, eye_shape=shape, eye_scale=1.15), yaw, turn, emo, monkeypatch)
                    over = max(worst_outside(head, e) for e in eyes)
                    if over > -ow * 0.5:
                        bad.append((shape, emo, yaw, turn, round(over, 1), round(ow, 1)))
                    gaps.append((eyes[1][0] - eyes[1][2]) - (eyes[0][0] + eyes[0][2]))
    return bad, gaps


@pytest.mark.parametrize("name", sorted(CAST))
def test_eyes_stay_inside_the_head_outline_when_turned(name, monkeypatch):
    bad, gaps = sweep(name, monkeypatch)
    assert not bad, (len(bad), bad[:8])
    assert min(gaps) > 0, min(gaps)                       # içeri alınan uzak göz öbür göze binmez


def test_front_face_eyes_are_not_moved(monkeypatch):
    """Düz bakan yüzde hiçbir göz taşmaz: düzeltme görünümü değiştirmez."""
    for name in CAST:
        before = draw(design(name), 0.0, 0.0, "neutral", monkeypatch)[1]
        monkeypatch.setattr(pp, "eyes_inside_head", lambda eyes, *a: eyes)
        assert draw(design(name), 0.0, 0.0, "neutral", monkeypatch)[1] == before
        monkeypatch.undo()


def test_old_unclamped_eye_is_caught(monkeypatch):
    """Bilerek eski davranış: göz içeri alınmaz; uzak göz dış çizgiyi aşar ve ölçü yakalar."""
    monkeypatch.setattr(pp, "eyes_inside_head", lambda eyes, *a: eyes)
    bad = sweep("cocuk", monkeypatch, shapes=("round",))[0]
    assert any(over > 0 for *_k, over, _ow in bad), bad[:6]
