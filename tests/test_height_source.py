"""Planlayıcının boyu çizilen boyla aynıdır (tek kaynak: puppet2d.designs_for): spec yokken, spec boy vermezken ve verirken.
İki sentetik proje; proje dosyası okunmaz."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import shot_motion as sm  # noqa: E402
import shot_planner as sp  # noqa: E402

CONFIGS = {"torun_dede": [("torun", 6), ("dede", 70)], "robo_zip": [("robo", 30), ("zip", 3)]}
SPECS = {"yok": (None, None), "boysuz": ({"hair_style": "short"}, {"build": 1.1}), "boylu": ({"height_m": 0.9}, {"height_m": 1.85}),
         "karisik": ({"height_m": 1.7}, None)}


def planned(tmp_path, name, specs):
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    chars = [{"id": c, "name": c, "age": a} for c, a in CONFIGS[name]]
    bible = {"id": name, "characters": chars}
    for (c, _a), spec in zip(CONFIGS[name], SPECS[specs]):
        if spec is not None:
            json.dump(spec, open(root / "assets" / f"{c}.spec.json", "w"))
    json.dump({}, open(root / "locations.json", "w"))
    ids = [c for c, _a in CONFIGS[name]]
    beat = {"t_start": 0, "t_end": 6, "scene_id": "S1", "shot_id": "p1", "location": "", "characters": ids, "action": "", "camera": "geniş",
            "choreo": {"motion": {ids[0]: {"kind": "walk", "x0": -1.4, "x1": -0.4}, ids[1]: {"kind": "idle", "x0": 0.9}}}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return sp.plan(str(ep), bible, str(root / "assets"), 0, 6), pp.designs_for(bible, str(root / "assets"))


@pytest.mark.parametrize("specs", sorted(SPECS))
@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_planner_height_is_the_drawn_height(tmp_path, name, specs):
    plan, des = planned(tmp_path, name, specs)
    assert {c: v["height"] for c, v in plan["characters"].items()} == {c: d["height"] for c, d in des.items()}
    beat = plan["beats"][0]
    for c, m in beat["motion"].items():                    # plan sonu konumu çizilen boyla hesaplanan konumdur
        assert m["x_end"] == round(sm.exit_x(m, 6.0, des[c]["height"], None), 4)


def test_planner_without_the_drawing_module_uses_the_same_default(tmp_path, monkeypatch):
    assert sp.DEFAULT_HEIGHT_M == pp.DEFAULT_HEIGHT_M
    monkeypatch.setattr(sp, "_pp", None)
    plan, _des = planned(tmp_path, "torun_dede", "boysuz")
    assert {v["height"] for v in plan["characters"].values()} == {pp.DEFAULT_HEIGHT_M}


def test_a_second_height_guess_in_the_planner_is_caught(tmp_path, monkeypatch):
    """Eski davranış (planlayıcının kendi 1.2 varsayımı) bu testin ölçüsüne takılır."""
    monkeypatch.setattr(pp, "designs_for", lambda *a: {})
    monkeypatch.setattr(sp, "spec_height", lambda *a: 1.2)
    plan, _ = planned(tmp_path, "torun_dede", "yok")
    monkeypatch.undo()
    assert {v["height"] for v in plan["characters"].values()} != {pp.DEFAULT_HEIGHT_M}
