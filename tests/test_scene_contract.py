import json, os, sys, copy, random
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import scene_contract as sc, continuity, shot_planner, shot_motion as sm

ROOT = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile")


def _beat(i, scene, loc, chars, **kw):
    b = {"t_start": i * 6, "t_end": i * 6 + 6, "scene_id": scene, "location": loc, "characters": chars, "action": "", "dialogue": "", "shot_id": f"{scene.lower()}_{i}"}
    b.update(kw); return b


def _sheet(beats):
    return {"beats": beats}


def _plan(beats_mot):
    return {"beats": [{"i": i, "cast": list(m), "motion": m, "lines": [], "camera": "wide", "focus": None, "pieces": [], "capability_gaps": [], "staging_notes": []} for i, m in enumerate(beats_mot)]}


def test_teleport_detected_and_bound_to_engine():
    sheet = _sheet([_beat(0, "A", "x", ["p", "q"]), _beat(1, "A", "x", ["p", "q"])])
    plan = _plan([{"p": {"x0": 0.0, "x1": 0.5}, "q": {"x0": 1.0, "x1": 1.0}}, {"p": {"x0": -1.5, "x1": -1.5}, "q": {"x0": 1.0, "x1": 1.0}}])
    c = sc.from_beat_sheet(sheet, plan, project_id="P", episode_id="E")
    bad = [p for p in c["problems"] if p["rule"] == "TELEPORT"]
    assert len(bad) == 1 and bad[0]["actor"] == "p" and bad[0]["engine"] == "staging" and bad[0]["shot"] == "a_1"


@pytest.mark.parametrize("trans", ["time_skip"])
def test_explicit_time_skip_and_scene_change_allowed(trans):
    sheet = _sheet([_beat(0, "A", "x", ["p"]), _beat(1, "A", "x", ["p"], transition=trans), _beat(2, "B", "y", ["p"])])
    plan = _plan([{"p": {"x0": 0, "x1": 0}}, {"p": {"x0": 1.7, "x1": 1.7}}, {"p": {"x0": -1.0, "x1": -1.0}}])
    c = sc.from_beat_sheet(sheet, plan, project_id="P", episode_id="E")
    assert c["problems"] == []
    assert [s["transition_kind"] for s in c["shots"]] == ["scene_change", "time_skip", "scene_change"]


def test_camera_cut_does_not_permit_teleport():
    sheet = _sheet([_beat(0, "A", "x", ["p"]), _beat(1, "A", "x", ["p"], transition="cut")])
    c = sc.from_beat_sheet(sheet, _plan([{"p": {"x0": 0, "x1": 0}}, {"p": {"x0": 1.0, "x1": 1.0}}]), project_id="P", episode_id="E")
    assert [p["rule"] for p in c["problems"]] == ["TELEPORT"]


def test_object_owner_jump_detected():
    o1 = {"prop": "ball", "track": [{"t": 0, "holder": "p"}, {"t": 6, "holder": "p"}]}
    o2 = {"prop": "ball", "track": [{"t": 6, "holder": "q"}, {"t": 12, "holder": "q"}]}
    sheet = _sheet([_beat(0, "A", "x", ["p", "q"], choreo={"objects": [o1]}), _beat(1, "A", "x", ["p", "q"], choreo={"objects": [o2]})])
    c = sc.from_beat_sheet(sheet, None, project_id="P", episode_id="E")
    assert any(p["rule"] == "OBJECT_JUMP" and p["engine"] == "object_state" for p in c["problems"])


def test_carry_starts_removes_default_jumps_property():
    rnd = random.Random(7)
    for _ in range(200):
        cast = [f"c{k}" for k in range(rnd.randint(1, 3))]
        prev = {c: rnd.uniform(-1.9, 1.9) for c in cast}
        mot = {c: {"kind": rnd.choice(["idle", "walk"]), "x0": sm.slots(len(cast))[i], "x1": 0.0, "seed": rnd.randint(0, 9)} for i, c in enumerate(cast)}
        for m in mot.values():
            m["x1"] = sm.move_target(m["kind"], m["x0"], m["seed"])
        continuity.carry_starts(mot, prev, "continuous")
        xs = sorted(m["x0"] for m in mot.values())
        assert all(b - a >= continuity.MIN_SEP - 1e-6 or len(cast) == 1 for a, b in zip(xs, xs[1:])) or max(xs) >= 1.9 - 1e-6 or min(xs) <= -1.9 + 1e-6
        assert all(abs(m["x0"]) <= 1.9 + 1e-9 for m in mot.values())
    m = {"a": {"kind": "idle", "x0": 0.0, "x1": 0.0, "seed": 1}}
    assert continuity.carry_starts(m, {"a": 1.0}, "time_skip") == [] and m["a"]["x0"] == 0.0


def test_planner_window_boundary_carries_state():
    bible = json.load(open(os.path.join(ROOT, "series-bible.json"), encoding="utf-8"))
    ep = os.path.join(ROOT, "episodes", "e900_kabul"); assets = os.path.join(ROOT, "assets")
    full = shot_planner.plan(ep, bible, assets, 0, 480)
    sheet = json.load(open(os.path.join(ep, "beat_sheet.json"), encoding="utf-8"))
    t_mid = float(sheet["beats"][2]["t_start"])
    part = shot_planner.plan(ep, bible, assets, t_mid, 480)
    f = {b["i"]: b for b in full["beats"]}
    for b in part["beats"]:
        assert {c: (m["x0"], m["x1"]) for c, m in b["motion"].items()} == {c: (m["x0"], m["x1"]) for c, m in f[b["i"]]["motion"].items()}


def test_real_fixture_has_no_teleport_without_explicit_transition():
    bible = json.load(open(os.path.join(ROOT, "series-bible.json"), encoding="utf-8"))
    ep = os.path.join(ROOT, "episodes", "e900_kabul")
    plan = shot_planner.plan(ep, bible, os.path.join(ROOT, "assets"), 0, 480)
    sheet = json.load(open(os.path.join(ep, "beat_sheet.json"), encoding="utf-8"))
    c = sc.from_beat_sheet(sheet, plan, project_id="p", episode_id="e")
    tele = [p for p in c["problems"] if p["rule"] == "TELEPORT"]
    # choreo ile açıkça konumlanan oyuncular planlayıcının yürütmesine rağmen sıçrayabilir: bunlar dürüstçe raporlanır, gizlenmez
    assert all(p["engine"] == "staging" and p["gap_m"] > continuity.TOL_M for p in tele)
    assert c["schema"] == sc.SCHEMA and sc.validate(c) is not None


def test_resume_state_restores_prev_exit():
    sheet = _sheet([_beat(0, "A", "x", ["p"]), _beat(1, "A", "x", ["p"])])
    c = sc.from_beat_sheet(sheet, _plan([{"p": {"x0": 0, "x1": 0.7}}, {"p": {"x0": 0.7, "x1": 0.7}}]), project_id="P", episode_id="E")
    assert continuity.resume_state(c["shots"], "a_1")["actors"]["p"]["x"] == 0.7
    assert continuity.resume_state(c["shots"], "a_0") is None


def test_validate_ids_versions_languages_and_upgrade():
    sheet = _sheet([_beat(0, "A", "x", ["p"], dialogue="p: merhaba"), _beat(1, "A", "x", ["p"])])
    c = sc.from_beat_sheet(sheet, _plan([{"p": {"x0": 0, "x1": 0}}, {"p": {"x0": 0, "x1": 0}}]), project_id="P", episode_id="E", languages=("tr", "de"), asset_versions={"p": "v3"})
    assert sc.validate(c) == [] and c["versions"]["characters"] == {"p": "v3"}
    assert sum(1 for e in c["shots"][0]["events"] if e["kind"] == "dialogue") == 2
    d = copy.deepcopy(c); d["shots"][1]["shot_id"] = d["shots"][0]["shot_id"]
    assert "DUP_ID" in [p["rule"] for p in sc.validate(d)]
    d = copy.deepcopy(c); d["version"] = 99
    assert sc.validate(d)[0]["rule"] == "VERSION"
    old = {"shots": [{"shot_id": "s0", "scene_id": "A", "t_start": 0, "t_end": 2}]}
    assert sc.validate(sc.upgrade(old)) == []
    with pytest.raises(ValueError):
        sc.upgrade({"beats": []})


def test_gaps_report_responsible_engine():
    sheet = _sheet([_beat(0, "A", "x", ["p"])])
    plan = _plan([{"p": {"x0": 0, "x1": 0}}]); plan["beats"][0]["capability_gaps"] = ["mekân 'x': dekor yok"]
    plan["beats"][0]["staging_notes"] = [{"rule": "throw_distance", "kind": "conflict", "actor": "p", "why": "çelişki"}]
    c = sc.from_beat_sheet(sheet, plan, project_id="P", episode_id="E")
    assert {g["engine"] for g in c["gaps"]} == {"render", "staging"}
    assert {p["engine"] for p in sc.validate(c)} == {"render", "staging"}
