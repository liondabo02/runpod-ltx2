"""Planlar arası süreklilik: ÇİZİLEN karakter konumu plan sınırında sıçramaz; dünya durumu birikimlidir (kadraj dışı oyuncu, anılmayan nesne);
bilerek eklenen hatalar sorumlu motora bağlanır. Ölçüm planlayıcının sayılarından değil, render2d.frame'in gerçekten çizdiği pozdan alınır."""
import copy, json, os, random, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import continuity, puppet2d as pp, render2d as r2, scene_contract as sc, shot_motion as sm, shot_planner as sp, turn_sheet as T

ROOT = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile")
EPS = 1e-4


def drawn_x(monkeypatch, plan, des, t):
    """O karede çizilen her oyuncunun dünya x'i (yakın plan ayıklaması kapatılır: ölçüm için herkes çizilir)."""
    got, real = {}, pp.draw_character

    def spy(cv, d, p, *a, **k):
        got.update({c: p["x"] for c, v in des.items() if v is d})
        return real(cv, d, p, *a, **k)
    with monkeypatch.context() as mp:
        mp.setattr(pp, "draw_character", spy)
        mp.setattr(r2, "_head_cropped", lambda *a: False)
        r2.frame(plan, des, t)
    return got


def boundary_gaps(monkeypatch, plan, des):
    """Sürekli sınırlarda, kadraj dışı kaldığı planlar dahil, her oyuncunun son görülen konumu ile ilk görülen konumu farkı."""
    last, gaps = {}, []
    for b in plan["beats"]:
        if b["transition_kind"] in continuity.FREE:
            last = {}
        for c, x in drawn_x(monkeypatch, plan, des, b["t_start"] + EPS).items():
            if c in last:
                gaps.append((abs(x - last[c]), b["shot_id"], c))
        last.update(drawn_x(monkeypatch, plan, des, b["t_end"] - EPS))
    return gaps


def mk(tmp_path, heights, beats, locations=None):
    root = str(tmp_path / "p"); ep = os.path.join(root, "episodes", "e1"); os.makedirs(ep); os.makedirs(os.path.join(root, "assets"))
    bible = {"series_id": "sentetik", "characters": [{"id": c, "name": c.title(), "age": 30, "role": "x"} for c in heights]}
    des = {}
    for ch in bible["characters"]:
        spec = {"species": "human", "height_m": heights[ch["id"]], "hair_style": "bob", "palette": {"hair": [0.2, 0.1, 0.1], "skin": [0.9, 0.7, 0.6], "shirt": [0.2, 0.5, 0.4], "shorts": [0.1, 0.2, 0.3], "accent": [1, 0.8, 0.2]}}
        json.dump(spec, open(os.path.join(root, "assets", ch["id"] + ".spec.json"), "w")); des[ch["id"]] = pp.derive_design(ch, spec)
    json.dump({"beats": beats}, open(os.path.join(ep, "beat_sheet.json"), "w"))
    json.dump(locations or {"yer_1": {"pieces": [["bins", 1.0]]}}, open(os.path.join(root, "locations.json"), "w"))
    return bible, ep, os.path.join(root, "assets"), des


def beat(i, cast, motion=None, objects=None, dur=8, scene="S1", **kw):
    b = {"t_start": i * dur, "t_end": (i + 1) * dur, "shot_id": f"s{i}", "scene_id": scene, "location": "yer_1", "characters": cast, "action": "", "camera": "geniş"}
    if motion is not None or objects is not None:
        b["choreo"] = {"motion": motion or {}, "objects": objects or []}
    b.update(kw); return b


def contract(ep, plan):
    return sc.from_beat_sheet(json.load(open(os.path.join(ep, "beat_sheet.json"))), plan, project_id="P", episode_id="E")


def M(kind, x0, x1=None):
    return {"kind": kind, "x0": x0, "x1": x0 if x1 is None else x1}


def test_every_motion_kind_starts_exactly_at_its_mark():
    for kind in ("idle", "look", "walk", "run", "carry", "reach", "sit", "wave", "laugh", "jump", "dance", "surprise"):
        for H in (0.7, 1.2, 2.3):
            for seed in range(9):
                assert abs(sm.pose_at(kind, 0.0, 8.0, seed, 0.4, 1.1, H, 0.45 * H)["x"] - 0.4) < 1e-9, (kind, H, seed)


@pytest.mark.parametrize("heights,seed", [({"mira": 1.55, "oz": 2.3, "pip": 0.7}, 1), ({"k1": 1.1, "k2": 1.9, "k3": 1.4}, 2)])
def test_drawn_positions_never_jump_with_random_conflicting_marks(tmp_path, monkeypatch, heights, seed):
    """Rastgele (birbiriyle çelişen) koreografi işaretleri, tepkiler ve kadrajdan çıkıp dönen oyuncular: çizilen konum sürekli kalır."""
    rnd = random.Random(seed); names = list(heights); beats = []
    for i in range(10):
        cast = sorted(rnd.sample(names, rnd.randint(1, 3)))
        mot = {c: M(rnd.choice(["idle", "look", "walk", "run", "carry", "reach", "laugh", "wave"]), round(rnd.uniform(-1.8, 1.8), 2), round(rnd.uniform(-1.8, 1.8), 2)) for c in cast if rnd.random() < 0.75}
        b = beat(i, cast, mot)
        if rnd.random() < 0.4:
            b["choreo"]["react"] = {cast[0]: {"t": 5.0, "kind": "surprise"}}
        beats.append(b)
    bible, ep, assets, des = mk(tmp_path, heights, beats)
    plan = sp.plan(ep, bible, assets, 0, 80)
    gaps = boundary_gaps(monkeypatch, plan, des)
    assert len(gaps) >= 8 and max(gaps)[0] < 0.02, max(gaps)
    assert not [p for p in contract(ep, plan)["problems"] if p["rule"] == "TELEPORT"]


def test_real_fixture_drawn_positions_and_contract_are_continuous(monkeypatch):
    bible = json.load(open(os.path.join(ROOT, "series-bible.json"), encoding="utf-8"))
    ep = os.path.join(ROOT, "episodes", "e900_kabul")
    plan = sp.plan(ep, bible, os.path.join(ROOT, "assets"), 0, 480)
    des = pp.designs_for(bible, os.path.join(ROOT, "assets"))   # render hattıyla aynı tasarım kaynağı (spec boyları)
    gaps = boundary_gaps(monkeypatch, plan, des)
    assert len(gaps) == 8 and max(gaps)[0] < 0.02, max(gaps)
    assert not [p for p in contract(ep, plan)["problems"] if p["rule"] in ("TELEPORT", "OBJECT_JUMP", "OBJECT_VANISH")]


def test_stationary_mark_is_kept_and_reached_by_walking_before_action(tmp_path, monkeypatch):
    bible, ep, assets, des = mk(tmp_path, {"a": 1.7}, [beat(0, ["a"], {"a": M("idle", -1.0)}), beat(1, ["a"], {"a": M("wave", 1.0)})])
    plan = sp.plan(ep, bible, assets, 0, 16)
    m = plan["beats"][1]["motion"]["a"]
    assert m["kind"] == "wave" and m["x0"] == 1.0                          # niyet (işaret + eylem) korunur
    arrive = m["approach"]["walk_s"]
    assert abs(m["approach"]["from"] - plan["beats"][0]["motion"]["a"]["x_end"]) < 1e-3
    xs = [drawn_x(monkeypatch, plan, des, 8 + k / 12)["a"] for k in range(0, 40)]
    assert max(abs(b - a) for a, b in zip(xs, xs[1:])) * 12 < 3.0 and abs(drawn_x(monkeypatch, plan, des, 8 + arrive + 0.05)["a"] - 1.0) < 0.03
    assert sm.segment(m, arrive - 0.01, 8)[0]["kind"] == "walk" and sm.segment(m, arrive + 0.01, 8)[0]["kind"] == "wave"


def test_offscreen_actor_keeps_position_until_return(tmp_path, monkeypatch):
    beats = [beat(0, ["a", "b"], {"a": M("idle", -1.2), "b": M("idle", 1.2)}), beat(1, ["a"], {"a": M("idle", -1.2)}), beat(2, ["a", "b"], {"a": M("idle", -1.2), "b": M("idle", -0.2)})]
    bible, ep, assets, des = mk(tmp_path, {"a": 1.5, "b": 1.8}, beats)
    plan = sp.plan(ep, bible, assets, 0, 24)
    assert abs(plan["beats"][2]["motion"]["b"]["approach"]["from"] - plan["beats"][0]["motion"]["b"]["x_end"]) < 1e-3
    assert max(boundary_gaps(monkeypatch, plan, des))[0] < 0.02


@pytest.mark.parametrize("trans", [{"transition": "time_skip"}, {"scene_id": "S2"}])
def test_free_transition_allows_new_marks_and_resets_world(tmp_path, trans):
    ob = [{"prop": "stone", "track": [{"t": 0, "at": [-1.0, 0.0]}, {"t": 8, "at": [-1.0, 0.0]}]}]
    bible, ep, assets, _ = mk(tmp_path, {"a": 1.5}, [beat(0, ["a"], {"a": M("idle", -1.0)}, ob), beat(1, ["a"], {"a": M("idle", 1.5)}, **trans)])
    plan = sp.plan(ep, bible, assets, 0, 16)
    assert "approach" not in plan["beats"][1]["motion"]["a"] and plan["beats"][1]["choreo"]["objects"] == []
    c = contract(ep, plan)
    assert sc.validate(c) == [] and continuity.resume_state(c["shots"], "s1") is None


def _object_project(tmp_path):
    held = {"prop": "stone", "track": [{"t": 0, "holder": "a"}, {"t": 8, "holder": "a"}]}
    ground = {"prop": "flower", "track": [{"t": 0, "at": [1.5, 0.0]}, {"t": 8, "at": [1.5, 0.0]}]}
    trash = {"prop": "bottle", "track": [{"t": 0, "holder": "b"}, {"t": 2, "holder": "b"}, {"t": 3.5, "at": "bin_green", "hide": True}]}
    both = {"a": M("idle", -0.5), "b": M("idle", 0.6)}
    beats = [beat(0, ["a", "b"], both, [held, ground, trash]), beat(1, ["a", "b"]), beat(2, ["b"]), beat(3, ["a", "b"])]
    return mk(tmp_path, {"a": 1.3, "b": 1.8}, beats, {"yer_1": {"pieces": [["bins", 1.0]]}})


def test_unmentioned_objects_persist_disposed_stay_gone_and_offscreen_holder_keeps_item(tmp_path):
    bible, ep, assets, des = _object_project(tmp_path)
    plan = sp.plan(ep, bible, assets, 0, 32)
    names = [sorted(o["prop"] for o in b["choreo"]["objects"]) for b in plan["beats"]]
    assert names[1] == ["flower", "stone"]                 # anılmasa da duruyor; imha edilen şişe geri gelmiyor
    assert names[2] == ["flower"]                          # taşıyan kadraj dışında: taş onunla
    assert names[3] == ["flower", "stone"]                 # döndüğünde taş yine elinde
    stone = next(o for o in plan["beats"][3]["choreo"]["objects"] if o["prop"] == "stone")
    assert stone["track"][0]["holder"] == "a"
    assert [o["prop"] for o, *_ in r2._objects_now(plan["beats"][3], [("a", des["a"], sm.base_pose(0.0), plan["beats"][3]["motion"]["a"], 0, 0)], 1.0)].count("stone") == 1
    c = contract(ep, plan)
    assert not [p for p in c["problems"] if p["rule"].startswith("OBJECT")], c["problems"]
    state = continuity.resume_state(c["shots"], "s3")      # birikmiş durum: s2'de görünmeyen oyuncu ve taşı da içinde
    assert state["objects"]["stone"]["holder"] == "a" and state["objects"]["bottle"]["hidden"] and "a" in state["actors"]


def test_render_window_start_gives_same_state_as_full_plan(tmp_path):
    bible, ep, assets, _ = _object_project(tmp_path)
    full = sp.plan(ep, bible, assets, 0, 32)
    for t0 in (8, 16, 24, 27.5):
        part = sp.plan(ep, bible, assets, t0, 32)
        ref = {b["i"]: b for b in full["beats"]}
        for b in part["beats"]:
            assert b["motion"] == ref[b["i"]]["motion"] and b["choreo"] == ref[b["i"]]["choreo"]


def _clean_contract(tmp_path):
    bible, ep, assets, _ = _object_project(tmp_path)
    c = contract(ep, sp.plan(ep, bible, assets, 0, 32))
    assert not [p for p in sc.validate(c) if p["rule"] != "STAGING_CONFLICT"]
    return c


def _drop_object(c): del c["shots"][1]["entry"]["objects"]["flower"]
def _move_ground(c): c["shots"][1]["entry"]["objects"]["flower"].update(at=[-1.5, 0.0], pos=[-1.5, 0.0])
def _resurrect(c): c["shots"][3]["entry"]["objects"]["bottle"] = {"holder": "b", "at": None, "pos": None, "hidden": False}
def _swap_owner_after_absence(c): c["shots"][3]["entry"]["objects"]["stone"]["holder"] = "b"
def _teleport_after_absence(c): c["shots"][3]["entry"]["actors"]["a"]["x"] += 1.0


@pytest.mark.parametrize("inject,rule,engine,shot", [(_drop_object, "OBJECT_VANISH", "object_state", "s1"), (_move_ground, "OBJECT_JUMP", "object_state", "s1"),
                                                     (_resurrect, "OBJECT_JUMP", "object_state", "s3"), (_swap_owner_after_absence, "OBJECT_JUMP", "object_state", "s3"),
                                                     (_teleport_after_absence, "TELEPORT", "staging", "s3")])
def test_injected_continuity_faults_are_caught_and_assigned(tmp_path, inject, rule, engine, shot):
    c = _clean_contract(tmp_path)
    inject(c)
    hits = [p for p in sc.validate(c) if p["rule"] == rule]
    assert hits and hits[0]["engine"] == engine and hits[0]["shot"] == shot, sc.validate(c)


def test_unreachable_mark_is_reported_not_teleported(tmp_path, monkeypatch):
    give = [{"prop": "ball", "track": [{"t": 0, "holder": "a"}, {"t": 0.3, "holder": "a"}, {"t": 0.8, "holder": "b"}, {"t": 2, "holder": "b"}]}]
    beats = [beat(0, ["a", "b"], {"a": M("idle", -1.8), "b": M("idle", 1.8)}, dur=2),
             dict(beat(1, ["a", "b"], {"a": M("idle", 1.4), "b": M("idle", 1.8)}, give, dur=2))]
    bible, ep, assets, des = mk(tmp_path, {"a": 1.7, "b": 1.7}, beats)
    plan = sp.plan(ep, bible, assets, 0, 4)
    whys = [n["why"] for n in plan["beats"][1]["staging_notes"] if n["kind"] == "conflict"]
    assert any("plan 2.00" in w for w in whys) and any("teması" in w for w in whys), whys
    assert max(boundary_gaps(monkeypatch, plan, des))[0] < 0.02          # yetişemese de ışınlanmaz
    assert any(p["rule"] == "STAGING_CONFLICT" and p["engine"] == "staging" for p in sc.validate(contract(ep, plan)))


def test_walk_through_another_actor_is_reported(tmp_path):
    beats = [beat(0, ["a", "b"], {"a": M("idle", -0.6), "b": M("idle", 0.6)}), beat(1, ["a", "b"], {"a": M("idle", 1.2), "b": M("idle", 0.6)})]
    bible, ep, assets, _ = mk(tmp_path, {"a": 1.5, "b": 1.8}, beats)
    notes = sp.plan(ep, bible, assets, 0, 16)["beats"][1]["staging_notes"]
    assert [n["actor"] for n in notes if n["rule"] == "continuity_crossing"] == ["a"]


def test_duplicate_object_identity_and_event_beyond_shot_are_flagged(tmp_path):
    two = [{"prop": "ball", "track": [{"t": 0, "at": [x, 0.0]}, {"t": 8, "at": [x, 0.0]}]} for x in (-1.0, 1.0)]
    late = [{"prop": "stone", "track": [{"t": 0, "holder": "a"}, {"t": 11, "holder": "a"}]}]
    bible, ep, assets, _ = mk(tmp_path, {"a": 1.5}, [beat(0, ["a"], {}, two + late)])
    rules = {p["rule"] for p in sc.validate(contract(ep, sp.plan(ep, bible, assets, 0, 8)))}
    assert {"DUP_OBJECT", "OBJECT_EVENT_OUTSIDE"} <= rules
    two[0]["id"], two[1]["id"] = "top_1", "top_2"
    bible, ep, assets, _ = mk(tmp_path / "b", {"a": 1.5}, [beat(0, ["a"], {}, two), beat(1, ["a"])])
    c = contract(ep, sp.plan(ep, bible, assets, 0, 16))
    assert sc.validate(c) == [] and set(c["shots"][1]["entry"]["objects"]) == {"top_1", "top_2"}


def test_render_preflight_uses_same_positions_as_drawing(tmp_path, monkeypatch):
    """Ön kontrol ayrı konum tahmini yapmaz: planlayıcının yürüttüğü karakterle atış geçerliyse render başlar; gerçekten yakınsa engellenir."""
    import shutil, render_worker as rw
    root = tmp_path / "k"; shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("render", "animatic"))
    bible = json.load(open(root / "series-bible.json", encoding="utf-8")); reached = []
    monkeypatch.setattr(rw.r2, "render_window", lambda plan_, des_, out_, **k: os.makedirs(out_, exist_ok=True) or reached.append(1) or {"missing": 1})
    m = rw.run(str(root / "episodes" / "e900_kabul"), bible, 0, 38, str(root))
    assert m["error"] == "FRAMES_MISSING" and reached, m
    # bilerek: plan başında, yürümeye vakit bırakmayan ve kutunun dibinden yapılan atış
    throw = [{"prop": "ball", "track": [{"t": 0, "holder": "a"}, {"t": 0.05, "holder": "a"}, {"t": 0.9, "at": "bin_green", "hide": True}]}]
    bible2, ep, assets, _ = mk(tmp_path, {"a": 1.6}, [beat(0, ["a"], {"a": M("idle", 1.0)}, throw)])
    m2 = rw.run(ep, bible2, 0, 8, os.path.dirname(assets))
    assert m2["error"] == "NESNE_IZI_GECERSIZ" and any("atış mesafesi" in p for p in m2["problems"]), m2
