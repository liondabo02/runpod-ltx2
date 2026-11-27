"""Yürüyüş duruş pozunda başlar ve biter. Yalnız sentetik değerler/projeler; proje dosyası okunmaz."""
import json, os, sys

import pytest
from PIL import ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import foot_slide  # noqa: E402
import motion_continuity as mc  # noqa: E402
import puppet2d as pp  # noqa: E402
import render2d as r2  # noqa: E402
import scenes2d as sc  # noqa: E402
import shot_motion as sm  # noqa: E402
import shot_planner as sp  # noqa: E402

FPS = 24
# (x0, x1, süre): iki yön, tek çevrimlik kısa yol, birkaç santimlik toplama, uzun yol
ROUTES = [(-1.0, 1.0, 4.0), (1.2, -0.8, 4.0), (0.0, 0.5, 3.0), (0.3, 0.2, 2.0), (-1.9, 1.9, 7.0)]


def rows(kind, H, x0, x1, dur, seed):
    return [mc.foot_row(sm.pose_at(kind, i / FPS, dur, seed, x0, x1, H, 0.0)) for i in range(int(dur * FPS) + 1)]


@pytest.mark.parametrize("H", [0.98, 1.3, 1.9])
@pytest.mark.parametrize("kind", ["walk", "carry", "run"])
def test_walk_starts_and_ends_in_rest_stance(kind, H):
    for x0, x1, dur in ROUTES:
        for seed in range(4):                                   # dört yürüyüş kişiliği
            m, why = mc.stance_report(rows(kind, H, x0, x1, dur, seed), H)
            assert not why, (kind, H, x0, x1, seed, why, m)


@pytest.mark.parametrize("H", [0.98, 1.9])
def test_arrival_does_not_add_foot_slide(H):
    for x0, x1, dur in ROUTES:
        for seed in range(4):
            for kind in ("walk", "run"):
                r = foot_slide.world_feet(sm, kind, H, x0=x0, x1=x1, dur=dur, seed=seed)
                s = foot_slide.slide_stats(r, H)
                assert s["n"] > 0 and s["max"] < 1e-6, (kind, H, x0, x1, seed, s)      # basılı ayak bütün karelerde sabit (p95 değil, en kötü)


def test_standing_still_walk_keeps_feet_at_rest():
    assert all(r[1:] == (0.0, 0.0, 0.0, 0.0) for r in rows("walk", 1.5, 0.4, 0.4, 2.0, 0))


@pytest.mark.parametrize("gait", ["walk", "run"])
@pytest.mark.parametrize("n", [1, 2, 3, 7])
def test_footstep_plan_is_ordered_and_reaches_the_goal(gait, n):
    st = sm.footsteps(gait, n)
    for side in "LR":
        prev = 0.0
        for p0, p1, _to in st[side]:
            assert prev - 1e-9 <= p0 < p1 <= n + 1e-9
            prev = p1
        assert st[side][-1][2] == pytest.approx(n)
    for i in range(n * 500 + 1):
        p = i / 500
        ups = [sm.foot_at(st[s], p)[1] > 0 for s in "LR"]
        assert gait == "run" or not all(ups), p                # yürüyüşte en az bir ayak hep yerde
        rel = [sm.foot_at(st[s], p)[0] - p for s in "LR"]
        assert max(map(abs, rel)) <= sm.STANCE[gait] / 2 + 1e-6, (p, rel)      # ayak gövdeden normal adımdan fazla uzaklaşmaz
        if gait == "walk":
            assert abs(rel[0] - rel[1]) <= 0.5 + 1e-6, (p, rel)                  # iki ayak arası yarım çevrimi geçmez


def test_stride_is_not_stretched_beyond_limit():
    for k in range(5, 400):
        total = k / 100 * 1.0
        n = sm.stride_count(total, 1.0)
        assert n >= 1 and (total / n <= sm.STRIDE_STRETCH_MAX + 1e-9)


def test_walk_only_offsets_fade_instead_of_switching():
    """Yürürken eklenen baş/gövde farkı (ağır ve caka yürüyüş) başlangıç ve varışta tek karede açılıp kapanmaz."""
    for seed in (1, 2):
        ps = [sm.pose_at("walk", i / FPS, 4.0, seed, -1.0, 1.0, 1.8, 0.0) for i in range(4 * FPS)]
        te = 0.85 * 4.0
        near = range(int((te - 0.1) * FPS), int((te + 0.2) * FPS))
        assert max(abs(ps[i + 1]["head"][0] - ps[i]["head"][0]) for i in near) < 0.07, seed
        assert max(abs(ps[i + 1]["lean"] - ps[i]["lean"]) for i in near) < 0.04, seed
        assert max(abs(ps[i + 1]["sq"] - ps[i]["sq"]) for i in near) < 0.02, seed


# ---------------------------------------------------------------- çizimden ölçü
def design(h, age):
    return pp.derive_design({"id": f"s{int(h * 100)}", "age": age}, {"height_m": h})


def drawing(d, pose, cam):
    st = {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0, "brow": 0.0, "pulse": 0.0}
    cv = pp.Cv(ss=1)
    pp.draw_character(cv, d, pose, st, cam.x(pose["x"]), cam.y(0.0), cam.s, 0.0)
    return cv.img


def changed_pixels(a, b):
    r, g, bl = ImageChops.difference(a, b).split()
    return ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v > 24 else 0).histogram()[255]


@pytest.mark.parametrize("h,age", [(0.98, 6), (1.9, 40)])
@pytest.mark.parametrize("direction", [1, -1])
def test_drawn_feet_at_arrival_match_rest_stance(h, age, direction):
    d = design(h, age)
    p = sm.pose_at("walk", 3.9, 4.0, 0, -direction * 1.0, direction * 1.0, h, 0.0)
    rest = {k: v for k, v in p.items() if k not in ("fL", "fR", "hL", "hR")}
    cam = sc.Cam(p["x"], 0.9, 1.2)
    ref = drawing(d, rest, cam)
    assert changed_pixels(drawing(d, p, cam), ref) <= 20                     # çizilen varış pozu = duruş pozu
    spread = dict(p, fL=0.15 * direction, fR=-0.10 * direction, hL=0.0, hR=0.0)      # eski motorun varış pozu
    assert changed_pixels(drawing(d, spread, cam), ref) > 200                 # ölçü ayrık duruşu görebiliyor


# ---------------------------------------------------------------- planlayıcı + render yolu
CONFIGS = {   # (kimlik, yaş, boy, x0, x1)
    "kucuk_saga": ("nil", 6, 0.98, -1.5, 0.4),
    "buyuk_sola": ("dede", 60, 1.9, 1.5, -0.6),
}


def planned(tmp_path, name):
    cid, age, h, x0, x1 = CONFIGS[name]
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": cid, "name": cid, "age": age}]}
    json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({}, open(root / "locations.json", "w")); json.dump(bible, open(root / "series-bible.json", "w"))
    base = {"scene_id": "S1", "location": "", "characters": [cid], "action": "", "camera": "orta"}
    beats = [dict(base, t_start=0, t_end=5, shot_id="p1", choreo={"motion": {cid: {"kind": "walk", "x0": x0, "x1": x1}}}),
             dict(base, t_start=5, t_end=8, shot_id="p2", choreo={"motion": {cid: {"kind": "idle", "x0": x1}}})]
    json.dump({"beats": beats}, open(ep / "beat_sheet.json", "w"))
    return sp.plan(str(ep), bible, str(root / "assets"), 0, 8), pp.designs_for(bible, str(root / "assets")), cid, h


def plan_rows(plan, des, cid, t0, t1):
    out = []
    for i in range(int(round((t1 - t0) * FPS))):
        its = r2.poses_at(plan, des, t0 + i / FPS)
        out.append(mc.foot_row(next(it for it in its if it[0] == cid)[2]))
    return out


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_planned_walk_then_next_shot_has_no_leg_pop(tmp_path, name):
    plan, des, cid, h = planned(tmp_path, name)
    r = plan_rows(plan, des, cid, 0.0, 8.0)
    m, why = mc.stance_report(r, h)
    assert not why, (why, m)
    assert max(abs(x[0] - r[0][0]) for x in r) > 1.0                       # gerçekten yürüdü


# ---------------------------------------------------------------- bilerek eklenen hatalar
def endless_gait(gait, n):
    """Eski davranış: açma/toplama adımı yok; ayaklar sürekli yürüyüşün ortasındaymış gibi yerleşir."""
    a = sm.STANCE[gait] / 2
    return {s: [(k + off + 0.5 - 2 * a, k + off + 0.5, k + off + 0.5 + 2 * a) for k in range(n)] for off, s in ((0.0, "R"), (0.5, "L"))}


def test_without_closing_steps_the_measure_catches_spread_legs(monkeypatch):
    monkeypatch.setattr(sm, "footsteps", endless_gait)
    m, why = mc.stance_report(rows("walk", 1.9, -1.0, 1.0, 4.0, 0), 1.9)
    assert any("varıştan sonra bacaklar ayrık" in w for w in why), (why, m)


def test_leg_pop_and_hanging_foot_are_caught():
    good = rows("walk", 1.5, -1.0, 1.0, 4.0, 0)
    popped = list(good); popped[1] = (popped[1][0], 0.16, 0.0, -0.1, 0.0)        # dururken bacaklar bir karede açılıyor
    assert any("sıçrıyor" in w for w in mc.stance_report(popped, 1.5)[1])
    hanging = good[:-8] + [(r[0], r[1], 0.05, r[3], r[4]) for r in good[-8:]]
    assert any("havada" in w for w in mc.stance_report(hanging, 1.5)[1])
    assert any("ayrık başlıyor" in w for w in mc.stance_report([(good[0][0], 0.15, 0.0, -0.1, 0.0)] + good[1:], 1.5)[1])
