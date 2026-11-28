"""Aksiyon okunabilirliği ölçüsü + aksiyon bloklaması/kamerası. Tamamen sentetik iki proje (farklı kimlik, boy, hedef yeri, atış yönü); proje dosyası okunmaz."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import action_staging  # noqa: E402
import puppet2d as pp  # noqa: E402
import readability as rd  # noqa: E402
import render_worker  # noqa: E402
import render2d as r2  # noqa: E402
import shot_planner as sp  # noqa: E402


def M(kind, x0, x1=None):
    return {"kind": kind, "x0": x0, "x1": x0 if x1 is None else x1}


# (atan, seyirci, atan boyu, seyirci boyu, kutu x, atanın x'i, seyircinin işareti)
CONFIGS = {
    "yetiskin_saga": ("dede", "torun", 1.8, 1.0, 1.0, -0.5, 0.45),
    "cocuk_sola": ("zip", "robo", 1.15, 1.5, -1.0, 0.1, -0.5),
}


def project(tmp_path, name):
    thrower, other, h1, h2, bin_x, tx, mark = CONFIGS[name]
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": thrower, "name": thrower, "age": 40}, {"id": other, "name": other, "age": 6}]}
    for cid, h in ((thrower, h1), (other, h2)):
        json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({f"yer_{name}": {"pieces": [["bins", bin_x]]}}, open(root / "locations.json", "w"))
    json.dump(bible, open(root / "series-bible.json", "w"))
    beat = {"t_start": 0, "t_end": 6, "scene_id": "S1", "shot_id": "p1", "location": f"yer_{name}", "characters": [thrower, other], "action": "", "camera": "yakın",
            "choreo": {"motion": {thrower: M("idle", tx), other: M("idle", mark)},
                       "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": thrower}, {"t": 2.0, "holder": thrower}, {"t": 3.2, "at": "bin_green", "hide": True}]}]}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return root, ep, bible


def planned(tmp_path, name):
    root, ep, bible = project(tmp_path, name)
    assets = str(root / "assets")
    return sp.plan(str(ep), bible, assets, 0, 6), pp.designs_for(bible, assets)


def throw(report):
    return next(r for r in report if r["event"] == "dispose")


def failed(r):
    return {f["metric"] for f in r["fails"]}


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_two_projects_pass_without_source_changes(tmp_path, name):
    plan, des = planned(tmp_path, name)
    r = throw(rd.measure_plan(plan, des))
    assert r["ok"], r["fails"]


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_bystander_in_corridor_is_moved_and_original_mark_reported(tmp_path, name):
    thrower, other, *_rest, mark = CONFIGS[name]
    plan, _ = planned(tmp_path, name)
    b = plan["beats"][0]
    note = next(n for n in b["staging_notes"] if n["rule"] == "blocking")
    assert note["kind"] == "adjusted" and note["actor"] == other and note["intent_x"] == pytest.approx(mark)
    assert b["motion"][other]["x0"] != pytest.approx(mark) and b["motion"][other]["kind"] == "idle"
    for lo, hi, *_ in action_staging.corridors(b["motion"], b["choreo"]["objects"], b["targets"]):
        half = action_staging.BODY_K * {"yetiskin_saga": 1.0, "cocuk_sola": 1.5}[name]
        assert not lo - half < b["motion"][other]["x0"] < hi + half


def test_participants_and_walkers_are_never_moved():
    objs = [{"prop": "bottle", "track": [{"t": 0, "holder": "a"}, {"t": 1, "holder": "a"}, {"t": 2, "at": "k", "hide": True}]}]
    mo = {"a": M("idle", -0.8), "w": M("walk", -1.5, 0.2)}
    before = json.loads(json.dumps(mo))
    assert action_staging.resolve(mo, objs, {"a": 1.7, "w": 1.0}, {"k": [0.8, 0.9]}, {}, "continuous", 6.0) == []
    assert mo == before


def test_no_free_position_is_a_conflict_not_silent():
    objs = [{"prop": "bottle", "track": [{"t": 0, "holder": "a"}, {"t": 1, "holder": "a"}, {"t": 2, "at": "k", "hide": True}]}]
    mo = {"a": M("idle", -1.9), "b": M("idle", 0.0)}
    notes = action_staging.resolve(mo, objs, {"a": 1.7, "b": 1.0}, {"k": [1.9, 0.9]}, {}, "continuous", 6.0)
    assert [n["kind"] for n in notes] == ["conflict"] and mo["b"]["x0"] == 0.0


def test_action_framing_is_constant_during_the_contact(tmp_path):
    plan, des = planned(tmp_path, "yetiskin_saga")
    b = plan["beats"][0]
    frames = [action_staging.framing(b, des, 1.4 + 0.1 * i, 100.0) for i in range(21)]
    assert all(f is not None and f == frames[0] for f in frames)
    assert action_staging.framing(b, des, 0.5, 100.0) is None and action_staging.framing(b, des, 5.0, 100.0) is None


# ------------------------------------------------ bilerek eklenen hatalar: ölçü her birini yakalamalı
def test_injected_wrong_camera_is_caught(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "yetiskin_saga")
    monkeypatch.setattr(action_staging, "framing", lambda *a: {"cx": -3.5, "cy": 1.6, "zoom": 1.7, "whole_cast": False})
    r = throw(rd.measure_plan(plan, des))
    assert not r["ok"] and {"object", "target", "hand:dede"} <= failed(r)


def test_injected_cut_during_action_is_caught(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "yetiskin_saga")
    real = action_staging.framing

    def cutting(beat, designs, lt, ppm):
        f = real(beat, designs, lt, ppm)
        return dict(f, zoom=f["zoom"] * 1.3) if f and lt > 2.4 else f
    monkeypatch.setattr(action_staging, "framing", cutting)
    assert "cuts" in failed(throw(rd.measure_plan(plan, des)))


def test_injected_occluder_in_front_of_hand_and_object_is_caught(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "cocuk_sola")                     # seyirci atandan uzun
    b = plan["beats"][0]
    b["motion"]["robo"] = dict(b["motion"]["robo"], x0=0.0, x1=0.0); b["motion"]["robo"].pop("approach", None)
    monkeypatch.setattr(action_staging, "draw_order", lambda beat, d, items: sorted(items, key=lambda it: it[0] == "robo"))
    r = throw(rd.measure_plan(plan, des))
    assert not r["ok"] and failed(r) & {"object", "hand:zip"}, r


def test_injected_blocked_target_is_caught(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "cocuk_sola")
    b = plan["beats"][0]
    b["motion"]["robo"] = dict(b["motion"]["robo"], x0=-1.0, x1=-1.0); b["motion"]["robo"].pop("approach", None)      # kutunun tam önü
    assert "target" in failed(throw(rd.measure_plan(plan, des)))


def test_missing_object_is_caught(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "yetiskin_saga")
    monkeypatch.setattr(r2.props2d, "draw", lambda *a, **k: None)
    assert "object" in failed(throw(rd.measure_plan(plan, des)))


def test_problems_name_the_responsible_engine():
    rep = [{"shot": "p", "event": "dispose", "object": "o", "by": "a", "to": None, "target": "k",
            "fails": [{"metric": "cuts", "why": "x"}, {"metric": "hand:a", "why": "y"}]}]
    assert [p["engine"] for p in rd.problems(rep)] == ["camera", "staging"]


def test_render_gate_blocks_unreadable_action_before_drawing_frames(tmp_path, monkeypatch):
    root, ep, bible = project(tmp_path, "yetiskin_saga")
    monkeypatch.setattr(action_staging, "framing", lambda *a: {"cx": -3.5, "cy": 1.6, "zoom": 1.7, "whole_cast": False})
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: pytest.fail("okunmayan aksiyon çizime girdi"))
    m = render_worker.run(str(ep), bible, 0, 6, str(root))
    assert m["status"] == "BLOCKED" and m["error"] == "AKSIYON_OKUNAMIYOR", m
    assert os.path.exists(ep / "render" / "readability.json")
    assert any("[camera]" in p or "[staging]" in p for p in m["problems"])


def test_injected_object_occlusion_is_measured_on_the_object_itself(tmp_path, monkeypatch):
    """Elde tutulan nesnenin önüne uzun bir oyuncu konur: yalnız el değil NESNE ölçütü de düşmeli."""
    plan, des = planned(tmp_path, "cocuk_sola")
    b = plan["beats"][0]
    b["motion"]["robo"] = dict(b["motion"]["robo"], x0=-0.15, x1=-0.15); b["motion"]["robo"].pop("approach", None)
    monkeypatch.setattr(action_staging, "draw_order", lambda beat, d, items: sorted(items, key=lambda it: it[0] == "robo"))
    r = throw(rd.measure_plan(plan, des))
    assert "object" in failed(r) and r["metrics"]["object"]["min"] < 0.3, r["metrics"]


def test_depth_order_participants_front_shorter_participant_foremost():
    items = [(c, {"height": h}, {"x": x}) for c, h, x in (("uzun", 1.9, 0.5), ("kisa", 1.0, 0.0), ("seyirci", 1.4, 1.5))]
    des = {c: d for c, d, _p in items}
    give = {"choreo": {"objects": [{"prop": "bottle", "track": [{"t": 0, "holder": "kisa"}, {"t": 1, "holder": "kisa"}, {"t": 2, "holder": "uzun"}]}]}}
    assert [i[0] for i in action_staging.draw_order(give, des, items)] == ["seyirci", "uzun", "kisa"]
    assert [i[0] for i in action_staging.draw_order({"choreo": {"objects": []}}, des, items)] == ["uzun", "seyirci", "kisa"]      # aksiyonsuz plan: uzun arkada (Y1: kısa oyuncu örtülmez)
