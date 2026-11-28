"""Ön / üç-çeyrek yürüyüşte kollar karede görünür biçimde ve aynı yandaki ayakla ters fazda sallanır.
Ölçü pp.hand_offset (çizimle aynı geometri) üzerinden; ayrıca çizilen elin yeri hand_offset ile karşılaştırılır. Yalnız sentetik değerler."""
import math, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import shot_motion as sm  # noqa: E402

FPS = 24
ROUTES = [(-1.0, 1.0, 4.0), (1.2, -0.8, 4.0), (-1.9, 1.9, 7.0)]
CLASSES = {"child": (4, 0.98), "adult": (35, 1.9)}
MIN_SWING = 0.10        # elin omuza göre yatay gidip gelmesi, boyun en az bu oranı
MIN_ANTIPHASE = -0.70   # el yatay yeri ile aynı yandaki ayağın (öbür ayağa göre) yeri arasındaki ilinti en çok bu


def design(cls):
    age, h = CLASSES[cls]
    return pp.derive_design({"id": f"s_{cls}", "age": age, "role": "erkek"}, {"height_m": h})


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = math.sqrt(sum((x - ma) ** 2 for x in a)); vb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) if va and vb else 0.0


def swing_stats(des, poses, side):
    other = "R" if side == "L" else "L"
    walking = [p for p in poses if pp.view_of(p) != "side"]
    rel = [pp.hand_offset(des, p, side)[0] - pp.shoulder_offset(des, p, side)[0] for p in walking]
    feet = [p["f" + side] - p["f" + other] for p in walking]
    return (max(rel) - min(rel)) / des["height"], corr(rel, feet)


def walk(H, route, seed, kind="walk"):
    x0, x1, dur = route
    return [sm.pose_at(kind, i / FPS, dur, seed, x0, x1, H, 0.0) for i in range(int(dur * FPS) + 1)]


@pytest.mark.parametrize("cls", sorted(CLASSES))
def test_arms_swing_against_the_same_side_foot(cls):
    des = design(cls)
    for route in ROUTES:
        for seed in range(4):
            for side in "LR":
                amp, ph = swing_stats(des, walk(des["height"], route, seed), side)
                assert amp >= MIN_SWING and ph <= MIN_ANTIPHASE, (route, seed, side, amp, ph)


@pytest.mark.parametrize("cls", sorted(CLASSES))
def test_swing_starts_and_ends_at_rest_and_never_jumps(cls):
    des = design(cls)
    for route in ROUTES:
        for seed in range(4):
            ps = walk(des["height"], route, seed)
            for side in "LR":
                assert abs(ps[0]["sw" + side]) < 1e-9 and abs(ps[-1]["sw" + side]) < 1e-9
                assert max(abs(b["sw" + side] - a["sw" + side]) for a, b in zip(ps, ps[1:])) < 0.25


def test_carrying_hands_do_not_swing():
    ps = walk(1.9, ROUTES[0], 0, "carry")
    assert not any("swL" in p or "swR" in p for p in ps)


def test_reach_blend_fades_the_swing_without_a_jump():
    """Yürürken uzanmaya geçiş: ağırlık 0'dan büyürken el tek adımda sıçramaz; 1'de salınım kalmaz."""
    des = design("adult")
    base = max(walk(1.9, ROUTES[0], 0), key=lambda p: abs(p.get("swR", 0.0)) if pp.view_of(p) != "side" else -1)
    assert abs(base["swR"]) > 0.2
    prev = pp.hand_offset(des, base, "R")
    for i in range(0, 101):
        p = dict(base, aL=list(base["aL"]), aR=list(base["aR"]))
        pp.arm_blend(des, p, "R", 0.5, 1.0, i / 100)
        cur = pp.hand_offset(des, p, "R")
        assert math.dist(prev, cur) < 0.04, (i, prev, cur)
        prev = cur
    assert "swR" not in p


def test_drawn_hand_follows_hand_offset_while_swinging(monkeypatch):
    des = design("adult")
    seen, real = [], pp._hand
    monkeypatch.setattr(pp, "_hand", lambda cv, pos, *a, **k: (seen.append(pos), real(cv, pos, *a, **k)))
    ppm = 200.0
    for p in walk(1.9, ROUTES[0], 0)[20:60:5]:
        if pp.view_of(p) == "side":
            continue
        seen.clear()
        pp.draw_character(pp.Cv(500, 600, ss=1), des, p, {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0}, 250, 560, ppm, 0.0)
        for side, pos in zip("LR", seen):
            dx, h = pp.hand_offset(des, p, side)
            assert abs((pos[0] - 250) / ppm - dx) < 0.03 and abs((560 - pos[1]) / ppm - h) < 0.05, (side, pos, dx, h)


def test_arms_without_swing_are_caught():
    """Bilerek eski davranış: salınım yok; ölçü yakalar."""
    des = design("adult")
    ps = [{k: v for k, v in p.items() if k not in ("swL", "swR")} for p in walk(1.9, ROUTES[0], 0)]
    amp, ph = swing_stats(des, ps, "L")
    assert not (amp >= MIN_SWING and ph <= MIN_ANTIPHASE), (amp, ph)


# ---------------------------------------------------------------- karede okunurluk: içe salınan eller birbirinin üstüne binmez
def min_hand_gap(des, poses):
    """İki el merkezi arasındaki en küçük ekran aralığı, el yarıçapı cinsinden (işaretli: R sağda kalmalı)."""
    r = pp.HAND_R_K * des["height"]
    return min((pp.hand_offset(des, p, "R")[0] - pp.hand_offset(des, p, "L")[0]) / r for p in poses if pp.view_of(p) != "side")


@pytest.mark.parametrize("cls", sorted(CLASSES))
def test_hands_never_merge_while_swinging(cls):
    des = design(cls)
    for route in ROUTES:
        for seed in range(4):
            assert min_hand_gap(des, walk(des["height"], route, seed)) >= 1.6, (route, seed)


def test_too_wide_swing_that_claps_the_hands_is_caught(monkeypatch):
    monkeypatch.setattr(sm, "ARM_SWING_K", 1.6)
    monkeypatch.setattr(sm, "ARM_SWING_MAX", 0.45)
    des = design("adult")
    assert min(min_hand_gap(des, walk(1.9, ROUTES[0], s)) for s in range(4)) < 1.6
