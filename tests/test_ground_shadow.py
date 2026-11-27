"""Yer gölgesi her görünüşte ayak altında çizilir. Ölçü çizilen pikselden; yalnız sentetik tasarımlar."""
import os, sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import puppet2d as pp  # noqa: E402

W, H, PPM_PX = 640, 760, 480.0
FY = H - 80
BG = (120, 170, 210)
VIEWS = {"on": ("front", 0.0), "uc_ceyrek_sag": ("front", 0.55), "uc_ceyrek_sol": ("front", -0.55), "profil_sag": ("side", 0.9), "profil_sol": ("side", -0.9)}
DESIGNS = {"cocuk": ({"id": "s_k", "age": 3, "role": "kız"}, {"height_m": 0.98}),
           "yetiskin": ({"id": "s_y", "age": 35, "role": "erkek"}, {"height_m": 1.9}),
           "etekli": ({"id": "s_e", "age": 30, "role": "anne (kadın)"}, {"height_m": 1.7, "lowerwear": "skirt"})}


def render(who, view, jump_h=0.0, walk=0.0):
    """jump_h: figür boyunun katı olarak zıplama."""
    des = pp.derive_design(*DESIGNS[who])
    kind, yaw = VIEWS[view]
    pose = {"x": 0.0, "z": jump_h * des["height"], "yaw": yaw, "lean": 0.0, "sq": 1.0, "head": [0.0, 0.0, 0.0],
            "aL": [0.0, 0.1], "aR": [0.0, -0.1], "lL": walk, "lR": -walk, "view": kind}
    cv = pp.Cv(W, H, ss=1)
    cv.img.paste(BG, (0, 0, W, H))
    pp.draw_character(cv, des, pose, {"mouth": "X", "blink": 0, "emotion": "neutral"}, W / 2, FY, PPM_PX / des["height"], 0.0)
    return cv.img.convert("RGB")


def shadow_box(img):
    """Zemin şeridindeki gölge renkli piksellerin (sol, üst, sağ, alt, adet) kutusu; yoksa None."""
    col = pp.shade(pp.SHADOW, 0.8)
    top = int(FY - PPM_PX * 0.06)
    px = img.load()
    hits = [(x, y) for y in range(top, int(FY + PPM_PX * 0.09)) for x in range(W) if px[x, y] == col]
    if not hits:
        return None
    xs, ys = [h[0] for h in hits], [h[1] for h in hits]
    return min(xs), min(ys), max(xs), max(ys), len(hits)


def problems(img, min_width=0.50):
    """Ayak altında gölge: yeterince geniş, ayak ortasını iki yandan saran, zeminin altına taşan bir leke."""
    box = shadow_box(img)
    if box is None:
        return ["gölge yok"]
    l, _t, r, b, _n = box
    out = []
    if r - l < PPM_PX * min_width:
        out.append(f"gölge dar: {r - l}px")
    if not (l < W / 2 - PPM_PX * 0.15 and r > W / 2 + PPM_PX * 0.15):
        out.append(f"gölge ayakların altında ortalı değil: {l}..{r}")
    if b < FY + PPM_PX * 0.03:
        out.append(f"gölge zemine inmiyor: alt {b}, zemin {FY}")
    return out


@pytest.mark.parametrize("who", sorted(DESIGNS))
@pytest.mark.parametrize("view", sorted(VIEWS))
def test_shadow_under_feet_in_every_view(who, view):
    for walk in (0.0, 0.8):
        assert not problems(render(who, view, walk=walk)), (walk, problems(render(who, view, walk=walk)))


@pytest.mark.parametrize("view", ["on", "profil_sag", "profil_sol"])
def test_shadow_stays_on_ground_and_narrows_in_a_jump(view):
    low, high = shadow_box(render("cocuk", view)), shadow_box(render("cocuk", view, jump_h=0.4))
    assert high[3] == low[3]                                     # alt kenar zeminde kalır
    assert (high[2] - high[0]) < (low[2] - low[0]) * 0.85


@pytest.mark.parametrize("view", sorted(VIEWS))
def test_missing_shadow_is_caught(view, monkeypatch):
    monkeypatch.setattr(pp, "ground_shadow", lambda *a, **k: None)
    assert problems(render("cocuk", view)) == ["gölge yok"]


def test_shadow_that_follows_the_jump_is_caught(monkeypatch):
    real = pp.ground_shadow
    monkeypatch.setattr(pp, "ground_shadow", lambda cv, fx, fy, Hh, jump: real(cv, fx, fy - jump, Hh, jump))
    assert shadow_box(render("cocuk", "profil_sag", jump_h=0.4)) is None
