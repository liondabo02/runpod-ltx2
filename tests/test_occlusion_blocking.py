"""Temassız planlarda bir oyuncu diğerini büyük ölçüde kapatamaz: çizim sırası (uzun arkada), piksel ölçüsü ve render kapısı.
İki ayrı sentetik proje (farklı kimlik, boy, yerleşim); proje dosyası okunmaz."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import action_staging  # noqa: E402
import puppet2d as pp  # noqa: E402
import readability as rd  # noqa: E402
import render_worker  # noqa: E402
import shot_planner as sp  # noqa: E402

DUR = 4.0
# (kısa kimlik, uzun kimlik, kısa boy, uzun boy, kısanın x'i, uzunun x'i) — uzun SAĞDA: x sırasıyla çizilseydi kısanın üstüne binerdi
CONFIGS = {"torun_dede": ("torun", "dede", 0.98, 1.9, -0.15, 0.15), "zip_robo": ("zip", "robo", 1.15, 1.75, 0.4, 0.62)}


def M(kind, x0, x1=None):
    return {"kind": kind, "x0": x0, "x1": x0 if x1 is None else x1}


def project(tmp_path, name, motion=None, heights=None):
    a, b, ha, hb, xa, xb = CONFIGS[name]
    ha, hb = heights or (ha, hb)
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": a, "name": a, "age": 6}, {"id": b, "name": b, "age": 40}]}
    for cid, h in ((a, ha), (b, hb)):
        json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({f"yer_{name}": {"pieces": []}}, open(root / "locations.json", "w"))
    json.dump(bible, open(root / "series-bible.json", "w"))
    beat = {"t_start": 0, "t_end": DUR, "scene_id": "S1", "shot_id": "p1", "location": f"yer_{name}", "characters": [a, b], "action": "", "camera": "geniş",
            "choreo": {"motion": motion or {a: M("idle", xa), b: M("idle", xb)}}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return root, ep, bible


def planned(tmp_path, name, **kw):
    root, ep, bible = project(tmp_path, name, **kw)
    assets = str(root / "assets")
    return sp.plan(str(ep), bible, assets, 0, DUR), pp.designs_for(bible, assets)


def x_order(beat, designs, items):
    """Eski davranış: temassız planda sıra yalnız x."""
    return sorted(items, key=lambda it: it[2]["x"])


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_short_actor_in_front_keeps_both_faces_open(tmp_path, name):
    plan, des = planned(tmp_path, name)
    assert rd.measure_occlusion(plan, des) == []
    cover = rd.actor_cover(plan, des, plan["beats"][0], 2.0)
    assert all(v["head"] >= rd.DEFAULTS["occl_head_visible"] and v["body"] >= rd.DEFAULTS["occl_visible"] for v in cover.values()), cover


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_old_x_order_is_caught(tmp_path, name, monkeypatch):
    monkeypatch.setattr(action_staging, "draw_order", x_order)
    plan, des = planned(tmp_path, name)
    rep = rd.measure_occlusion(plan, des)
    short = CONFIGS[name][0]
    assert [r["actor"] for r in rep] == [short] and rep[0]["by"] == CONFIGS[name][1], rep
    why = rd.occlusion_problems(rep)[0]
    assert why["engine"] == "staging" and why["rule"] == "ACTOR_OCCLUDED"


def test_brief_crossing_is_allowed_but_the_same_overlap_held_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(action_staging, "draw_order", x_order)      # örtme üretebilmek için eski sıra
    name = "torun_dede"
    plan, des = planned(tmp_path, name, motion={"torun": M("idle", 0.0), "dede": M("idle", 1.6)})
    assert rd.measure_occlusion(plan, des) == []
    plan, des = planned(tmp_path / "held", name, motion={"torun": M("idle", 0.0), "dede": M("idle", 0.2)})
    rep = rd.measure_occlusion(plan, des)
    assert rep and rep[0]["seconds"] > rd.DEFAULTS["occl_max_s"]
    assert rd.measure_occlusion(plan, des, {"occl_max_s": DUR}) == []


def test_equal_heights_stacked_are_reported(tmp_path):
    """Boylar eşitse çizim sırası kurtaramaz: üst üste duran iki oyuncu bloklama sorunu olarak bildirilir."""
    plan, des = planned(tmp_path, "torun_dede", motion={"torun": M("idle", 0.0), "dede": M("idle", 0.1)}, heights=(1.7, 1.7))
    rep = rd.measure_occlusion(plan, des)
    assert rep and min(rep[0]["body"], rep[0]["head"]) < 0.6, rep


def test_layer_order_does_not_flip_while_actors_cross(tmp_path):
    des = {"a": {"height": 1.0}, "b": {"height": 1.8}}
    orders = set()
    for xa in (-1.0, -0.2, 0.2, 1.0):
        items = [("a", des["a"], {"x": xa}), ("b", des["b"], {"x": 0.0})]
        orders.add(tuple(i[0] for i in action_staging.draw_order({}, des, items)))
    assert orders == {("b", "a")}


def run_gate(root, ep):
    return render_worker.run(str(ep), json.load(open(root / "series-bible.json", encoding="utf-8")), 0, DUR, str(root))


def test_render_gate_blocks_long_occlusion(tmp_path, monkeypatch):
    monkeypatch.setattr(action_staging, "draw_order", x_order)
    monkeypatch.setattr(render_worker.r2 if hasattr(render_worker, "r2") else __import__("render2d"), "render_window",
                        lambda *a, **k: pytest.fail("örtülü blokaj çizime girdi"))
    root, ep, _b = project(tmp_path, "torun_dede")
    res = run_gate(root, ep)
    assert res["status"] == "BLOCKED" and res["error"] == "OYUNCU_ORTULUYOR", res
    assert "[staging] ACTOR_OCCLUDED" in res["problems"][0]
    saved = json.load(open(ep / "render" / "occlusion.json", encoding="utf-8"))
    assert saved["occluded"] and saved["thresholds"]["occl_head_visible"] == rd.DEFAULTS["occl_head_visible"]
    assert not (ep / "render" / "frames").exists()
