"""Yakın planda alt kadraj kenarı bacakların ortasından ya da tutulan nesneden geçmez; üst beden kesmesi kasıtlı ve işaretlidir.
Ölçü çizimle aynı kamera kod yolundan. İki sentetik proje (farklı kimlik ve boy); proje dosyası okunmaz."""
import json, os, sys

import pytest
from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import readability as rd  # noqa: E402
import render2d as r2  # noqa: E402
import render_worker  # noqa: E402
import scenes2d as sc  # noqa: E402
import shot_planner as sp  # noqa: E402

DUR = 4.0
CONFIGS = {"torun_dede": ("dede", "torun", 1.9, 0.98), "robo_zip": ("robo", "zip", 1.65, 1.25)}


def project(tmp_path, name, camera="yakın plan", kinds=None, cast=None):
    tall, short, ht, hs = CONFIGS[name]
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": tall, "name": tall, "age": 40}, {"id": short, "name": short, "age": 6}]}
    for cid, h in ((tall, ht), (short, hs)):
        json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({}, open(root / "locations.json", "w")); json.dump(bible, open(root / "series-bible.json", "w"))
    cast = [tall if c == "tall" else short for c in (cast or ["tall", "short"])]
    kinds = kinds or {}
    motion = {c: {"kind": kinds.get(c, "idle"), "x0": -0.9 + 1.8 * i} for i, c in enumerate(cast)}
    beat = {"t_start": 0, "t_end": DUR, "scene_id": "S1", "shot_id": "p1", "location": "", "characters": cast, "action": "", "camera": camera,
            "choreo": {"motion": motion}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return root, ep, bible


def planned(tmp_path, name, **kw):
    root, ep, bible = project(tmp_path, name, **kw)
    assets = str(root / "assets")
    return sp.plan(str(ep), bible, assets, 0, DUR), pp.designs_for(bible, assets)


def old_framing(cy, zoom, *a, **k):
    return cy, zoom, None


@pytest.mark.parametrize("cast", [["tall", "short"], ["short", "tall"], ["tall"], ["short"]])
@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_close_shot_never_cuts_through_the_legs(tmp_path, name, cast):
    plan, des = planned(tmp_path, name, cast=cast)
    rep = rd.measure_crop(plan, des)
    assert rep["violations"] == [], rep
    for i in range(int(DUR * 4)):
        tr = {}
        r2.frame(plan, des, i / 4, trace=tr, camera_only=True)
        d, cam = des[tr["focus"]], tr["cam"]
        assert cam.y(d["height"] * r2.HEAD_TOP_K) >= r2.HEAD_MARGIN_PX - 0.5          # baş üstten de kesilmez
        assert cam.y(0.0) <= r2.FEET_MAX_PX + 0.5 or r2.frame_bottom(cam) >= r2.hip_height(d)


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_intentional_upper_body_crop_is_marked(tmp_path, name):
    plan, des = planned(tmp_path, name, cast=["tall"])
    rep = rd.measure_crop(plan, des)
    assert rep["intentional"] and all(r["crop"] == "upper_intentional" for r in rep["intentional"]), rep


def test_camera_only_is_the_same_decision_as_the_drawn_frame(tmp_path):
    plan, des = planned(tmp_path, "torun_dede")
    for t in (0.5, 2.0, 3.5):
        a, b = {}, {}
        r2.frame(plan, des, t, trace=a)
        r2.frame(plan, des, t, trace=b, camera_only=True)
        assert (a["cam"].cx, a["cam"].cy, a["cam"].z, a["preset"], a["crop"]) == (b["cam"].cx, b["cam"].cy, b["cam"].z, b["preset"], b["crop"])
        assert [k for kind, k, *_ in a["layers"] if kind == "character"] and set(b["drawn"]) == {k for kind, k, *_ in a["layers"] if kind == "character"}


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_old_framing_is_caught_and_blocks_the_render(tmp_path, name, monkeypatch):
    monkeypatch.setattr(r2, "crop_safe_framing", old_framing)
    root, ep, bible = project(tmp_path, name, cast=["tall"])
    assets = str(root / "assets")
    rep = rd.measure_crop(sp.plan(str(ep), bible, assets, 0, DUR), pp.designs_for(bible, assets))
    assert [v["rule"] for v in rep["violations"]] == ["ALTTAN_KAZARA_KESIK"], rep
    why = rd.crop_problems(rep)[0]
    assert why["engine"] == "camera" and why["shot"] == "p1"
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: pytest.fail("kapı geçildi"))
    out = render_worker.run(str(ep), bible, 0, DUR, str(root))
    assert out["status"] == "BLOCKED" and out["error"] == "KADRAJ_ALTTAN_KESIK", out
    assert json.load(open(ep / "render" / "framing_crop.json", encoding="utf-8"))["violations"]


def design(name, h, cls="adult"):
    return {"height": h, "class": cls}


@pytest.mark.parametrize("h,cls", [(1.9, "adult"), (0.98, "child"), (0.7, "toddler")])
@pytest.mark.parametrize("zoom", [1.25, 1.6, 1.8, 2.3])
def test_framing_rule_for_held_object_sitting_and_jumping(h, cls, zoom):
    d = design("x", h, cls); hip = r2.hip_height(d); cy = h * 0.8
    ground = lambda c, z: pp.H / 2 + c * sc.BASE_PPM * z
    bottom = lambda c, z: c - pp.H / 2 / (sc.BASE_PPM * z)
    for held in (None, h * 0.62, hip + 0.02 * h, hip * 0.5):
        c, z, mode = r2.crop_safe_framing(cy, zoom, d, sc.BASE_PPM, {"held": held})
        assert ground(c, z) <= r2.FEET_MAX_PX + 0.5 or bottom(c, z) >= hip
        if held is not None and mode == "upper":
            assert pp.H - (c - held) * sc.BASE_PPM * z - pp.H / 2 <= pp.H - rd.DEFAULTS["crop_object_margin_px"]
        if held is not None and held < hip and ground(cy, zoom) > r2.FEET_MAX_PX:
            assert mode == "full"
    c, z, mode = r2.crop_safe_framing(cy, zoom, d, sc.BASE_PPM, {"sink": 0.2 * h})
    assert mode == "full" and ground(c, z) <= r2.FEET_MAX_PX + 0.5
    rise = 0.15 * h
    c, z, _m = r2.crop_safe_framing(cy, zoom, d, sc.BASE_PPM, {"rise": rise})
    assert pp.H / 2 - (h * r2.HEAD_TOP_K + rise - c) * sc.BASE_PPM * z >= r2.HEAD_MARGIN_PX - 0.5      # zıplayan baş kadrajda


def test_framing_that_already_shows_the_feet_is_unchanged():
    assert r2.crop_safe_framing(0.78, 1.6, design("x", 0.98, "child"), sc.BASE_PPM) == (0.78, 1.6, "full")


def _fringe_top(zoom):
    cv = pp.Cv(ss=1); cv.img.paste((1, 2, 3), (0, 0, pp.W, pp.H))
    sc._grass_fringe(cv, sc.Cam(0.0, 1.0, zoom), 0.0)
    return ImageChops.difference(cv.img, Image.new("RGB", cv.img.size, (1, 2, 3))).getbbox()[1]


def test_foreground_grass_does_not_grow_over_the_body_in_close_shots(monkeypatch):
    assert min(_fringe_top(z) for z in (1.0, 1.6, 2.0, 2.39)) >= 636
    monkeypatch.setattr(sc, "FRINGE_MAX_PPM", 10_000.0)
    assert _fringe_top(2.0) < 600


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_low_held_object_from_the_real_track_stays_in_frame_and_ignoring_it_is_caught(tmp_path, name, monkeypatch):
    tall = CONFIGS[name][0]
    root, ep, bible = project(tmp_path, name, cast=["tall"])
    sheet = json.load(open(ep / "beat_sheet.json", encoding="utf-8"))
    sheet["beats"][0]["choreo"]["objects"] = [{"prop": "shovel", "track": [{"t": 0, "holder": tall}, {"t": DUR, "holder": tall}]}]
    json.dump(sheet, open(ep / "beat_sheet.json", "w"))
    assets = str(root / "assets")
    plan, des = sp.plan(str(ep), bible, assets, 0, DUR), pp.designs_for(bible, assets)
    assert r2.shot_needs(plan, des, plan["beats"][0], tall)["held"] < r2.hip_height(des[tall])
    assert rd.measure_crop(plan, des)["violations"] == []
    monkeypatch.setattr(r2, "shot_needs", lambda *a: {})
    assert [v["rule"] for v in rd.measure_crop(plan, des)["violations"]] == ["KONU_NESNE_ALTTAN_KESIK"]
