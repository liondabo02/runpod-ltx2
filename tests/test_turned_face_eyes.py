"""Yüz yana dönükken perspektif: yüzün döndüğü yandaki (uzak) göz daralır, karşı yandaki (yakın) göz geniş kalır.
Ölçü çizilen karedeki göz akı pikselinden; sağ ve sol dönüş birbirinin tersi. Yalnız sentetik değerler."""
import os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402

WHITE = (255, 255, 255)
CAST = {"child": (4, 0.98), "adult": (35, 1.9)}


def eye_whites(name, yaw, monkeypatch):
    """(ekranda soldaki, sağdaki) göz akının piksel sayısı."""
    age, h = CAST[name]
    des = pp.derive_design({"id": f"s_{name}", "age": age, "role": "erkek"}, {"height_m": h})
    p = pp._standing(0.0)
    p.update(head=[0.0, 0.0, 0.0], aL=[0.0, 0.1], aR=[0.0, -0.1], lL=0.0, lR=0.0, yaw=yaw, view="three_quarter" if yaw else "front")
    centres, real = [], pp.Cv.ellipse

    def spy(self, cx, cy, rx, ry, fill, *a, **k):
        if fill == WHITE and rx > 8:                       # göz akı elipsi (parıltı noktası çok daha küçük)
            centres.append((cx, cy, ry))
        real(self, cx, cy, rx, ry, fill, *a, **k)

    cv = pp.Cv(600, 700, ss=1)
    cv.img.paste((0, 120, 0), (0, 0, 600, 700))            # zeminde beyaz piksel olmasın
    with monkeypatch.context() as m:
        m.setattr(pp.Cv, "ellipse", spy)
        pp.draw_character(cv, des, p, {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0}, 300, 660, 560.0 / h, 0.0)
    assert len(centres) == 2, centres
    (lx, y, ry), (rx_, _y, _ry) = sorted(centres)
    img = cv.img.convert("RGB").load()
    mid = (lx + rx_) / 2
    counts = [0, 0]
    for yy in range(int(y - ry * 1.2), int(y + ry * 1.2)):
        for xx in range(int(lx - 60), int(rx_ + 60)):
            if 0 <= xx < 600 and img[xx, yy] == WHITE:
                counts[xx > mid] += 1
    return tuple(counts)


def turned_ok(name, monkeypatch):
    left, right = eye_whites(name, 0.6, monkeypatch)       # sağa dönük: sağdaki göz uzak
    r_ok = right < left * 0.92
    left, right = eye_whites(name, -0.6, monkeypatch)      # sola dönük: soldaki göz uzak
    return r_ok and left < right * 0.92


@pytest.mark.parametrize("name", sorted(CAST))
def test_far_eye_is_the_narrow_one(name, monkeypatch):
    assert turned_ok(name, monkeypatch)


@pytest.mark.parametrize("name", sorted(CAST))
def test_front_eyes_are_equal(name, monkeypatch):
    left, right = eye_whites(name, 0.0, monkeypatch)
    assert abs(left - right) <= 0.05 * max(left, right), (left, right)


@pytest.mark.parametrize("name", sorted(CAST))
def test_old_swapped_perspective_is_caught(name, monkeypatch):
    """Bilerek eski davranış: yüzün döndüğü yanın TERSİNDEKİ göz daraltılır; ölçü yakalar."""
    monkeypatch.setattr(pp, "far_eye", lambda sg, face: sg * face < -0.2)
    assert not turned_ok(name, monkeypatch)
