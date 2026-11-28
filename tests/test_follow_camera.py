"""Takip planı ve kurgu: kamera tek karede 'atlamaz'; yürüyen oyuncu izlenirken kadraj nabız gibi atmaz. İki farklı sentetik proje."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import readability  # noqa: E402
import render2d as r2  # noqa: E402
import shot_cuts  # noqa: E402
import shot_planner as sp  # noqa: E402
import puppet2d as pp  # noqa: E402
from test_listener_reaction import PROJECTS, line, make_project  # noqa: E402
import listener_reaction as lr  # noqa: E402


def pbeat(i, t0, t1, camera="wide", **kw):
    return dict({"i": i, "t_start": t0, "t_end": t1, "camera": camera, "cast": ["a", "b"], "loc": "x", "focus": "a",
                 "transition_kind": "continuous"}, **kw)


# ---------------------------------------------------------------- kurgu listesi (saf)
def test_near_identical_presets_are_one_shot_with_a_single_push():
    b = pbeat(0, 0.0, 9.0)                                      # eski liste: geniş, orta (3.5), ... -> %5-10 atlama
    assert [s["preset"] for s in shot_cuts.shots(b)][0] == "wide"
    prev = None
    for k in range(int(9.0 * 12)):
        preset, ph, shot = shot_cuts.at(b, k / 12)
        if prev and prev[2] == shot:
            assert preset == prev[0] and 0.0 <= ph - prev[1] < 0.1
        elif prev:
            assert shot_cuts.family(preset) != shot_cuts.family(prev[0])
        prev = (preset, ph, shot)


def test_no_sliver_shot_at_beat_end():
    for dur in (5.1, 7.2, 7.9, 10.6, 14.3):
        for i in range(4):
            b = pbeat(i, 0.0, dur, "close")
            assert all(s["end"] - s["start"] >= shot_cuts.MIN_CUT_S - 1e-9 for s in shot_cuts.shots(b)), (dur, i)


def test_continuous_beat_boundary_keeps_the_shot_and_a_scene_change_does_not():
    a, b = pbeat(0, 0.0, 4.0, "wide"), pbeat(1, 4.0, 8.0, "medium")
    shot_cuts.link(a, b)
    assert shot_cuts.at(b, 0.0)[:2] == ("wide", 1.0)             # önceki çekim sürer: aynı tür, aynı yaklaşma
    for change in ({"transition_kind": "scene_change"}, {"loc": "y"}, {"cast": ["a"]}, {"t_start": 4.5}):
        c = dict(b, **change)
        shot_cuts.link(a, c)
        assert shot_cuts.at(c, 0.0)[:2] == ("medium", 0.0), change


def test_close_shot_continues_only_on_the_same_face():
    a, b = pbeat(0, 0.0, 4.0, "close"), pbeat(1, 4.0, 8.0, "close")
    shot_cuts.link(a, b)
    assert shot_cuts.at(b, 0.0)[1] == 1.0
    c = dict(b, focus="b")
    shot_cuts.link(a, c)
    assert shot_cuts.at(c, 0.0)[1] == 0.0


# ---------------------------------------------------------------- gerçek kare yolu
def walking_project(tmp_path, name, camera="geniş"):
    """İki vuruş: biri yürürken diğeri konuşur; ikinci vuruş sürekli geçiş."""
    plan, designs = make_project(tmp_path, name, ["Bugün hava güzel.", "Aferin sana!"])
    root = tmp_path / name
    a, b = [c[0] for c in PROJECTS[name]][:2]
    sheet = {"beats": [
        {"t_start": 0, "t_end": 9, "characters": [a, b], "camera": camera, "location": "yer", "action": "Yürürler.", "scene_id": "S",
         "choreo": {"motion": {a: {"kind": "walk", "x0": -1.6, "x1": 0.2}, b: {"kind": "idle", "x0": 1.2}}}},
        {"t_start": 9, "t_end": 18, "characters": [a, b], "camera": "orta", "location": "yer", "action": "Yürürler.", "scene_id": "S",
         "choreo": {"motion": {a: {"kind": "walk", "x0": 0.2, "x1": -1.4}, b: {"kind": "idle", "x0": 1.2}}}}]}
    (root / "ep" / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    items = [{"beat": 0, "char": a, "text": "Bak buraya.", "duration_s": 2.0, "start_s": 1.0}]
    (root / "ep" / "voice_manifest.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    import shot_planner as sp
    return sp.plan(str(root / "ep"), {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]},
                   str(root / "assets"), 0, 18), designs, a


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_no_edit_pop_while_following_a_walker(tmp_path, name):
    plan, designs, _walker = walking_project(tmp_path, name)
    pops = readability.camera_pops(plan, designs)
    assert readability.camera_pop_problems(pops) == [], pops


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_gate_catches_the_old_three_and_a_half_second_recut(tmp_path, name, monkeypatch):
    """Bilerek bozma: eski kurgu (3,5 sn'de bir yaklaşmayı başa alan genel/orta yeniden kesme) yakalanır."""
    plan, designs, _walker = walking_project(tmp_path, name)

    def old(beat, lt):
        dur = beat["t_end"] - beat["t_start"]
        sub = int(lt / 3.5)
        preset = beat["camera"] if sub == 0 else ("wide", "medium", "wide", "wide")[sub % 4]
        return preset, (lt % 3.5) / 3.5 if dur > 5 else lt / dur, sub
    monkeypatch.setattr(r2.shot_cuts, "at", old)
    assert readability.camera_pop_problems(readability.camera_pops(plan, designs))


def zoom_steps(plan, designs, t0, t1):
    zs = []
    for k in range(int(t0 * 12), int(t1 * 12)):
        tr = {}
        r2.frame(plan, designs, k / 12, trace=tr, camera_only=True)
        zs.append((tr["preset"], tr["focus"], tr["cam"].s))
    return [abs(b[2] / a[2] - 1.0) for a, b in zip(zs, zs[1:]) if a[:2] == b[:2] == ("close", a[1])]


def close_walk_with_stress(tmp_path, name, moving):
    plan, designs, a = walking_project(tmp_path, name)
    beat = plan["beats"][0]
    beat["camera"] = "close"
    beat["lines"] = [{"char": a, "start": 0.2, "end": 3.4, "mood": "neutral",
                      "cues": [[t / 10, t / 10 + 0.1, 1.0, "D" if t % 5 == 0 else "X"] for t in range(32)]}]
    if not moving:
        beat["motion"][a].update(kind="idle", x1=beat["motion"][a]["x0"])
    return plan, designs


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_stressed_speech_does_not_pump_the_follow_shot(tmp_path, name):
    plan, designs = close_walk_with_stress(tmp_path, name, moving=True)
    steps = zoom_steps(plan, designs, 1.5, 3.2)
    assert len(steps) > 8 and max(steps) < 0.01, max(steps)


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_still_close_up_keeps_the_stress_punch_and_breaking_it_is_visible(tmp_path, name, monkeypatch):
    plan, designs = close_walk_with_stress(tmp_path, name, moving=False)
    if max(zoom_steps(plan, designs, 1.5, 3.2)) < 0.01:                 # üst beden kadrajında itme küçüktür
        pytest.skip("bu boyda duran yakın planda itme eşik altında")
    plan, designs = close_walk_with_stress(tmp_path / "b", name, moving=True)
    monkeypatch.setattr(r2, "follow_steadiness", lambda *a, **k: 1.0)    # bozma: takip ayrımı kapalı
    assert max(zoom_steps(plan, designs, 1.5, 3.2)) >= 0.01


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_listener_shot_does_not_pump_to_the_speakers_stress(tmp_path, name):
    plan, designs = close_walk_with_stress(tmp_path, name, moving=False)
    beat = plan["beats"][0]
    line = beat["lines"][0]
    mid = line["start"] + 0.62 * (line["end"] - line["start"])          # uzun replikin ortasında dinleyene kesme
    steps = zoom_steps(plan, designs, mid + 0.1, mid + 0.8)
    assert steps and max(steps) < 0.01, steps


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_chunked_window_gets_the_same_edit_as_the_whole_plan(tmp_path, name):
    """Parça parça üretim: ikinci vuruştan başlayan pencerenin kurgusu, bütün planınkiyle aynıdır."""
    import shot_planner as sp
    whole, _designs, _a = walking_project(tmp_path, name)
    root = tmp_path / name
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}
    part = sp.plan(str(root / "ep"), bible, str(root / "assets"), 9, 18)
    assert part["beats"][0]["cut_in"] == whole["beats"][1]["cut_in"]
    assert shot_cuts.shots(part["beats"][0]) == shot_cuts.shots(whole["beats"][1])


# ---------------------------------------------------------------- yakın çekimin kadraj ihtiyacı: kesintisiz çekim boyunca tek değer
def close_chain(tmp_path, name, second="dance", camera_b="yakın", objects=None):
    """İki sürekli vuruşta aynı yüzde yakın plan; ikinci vuruşta kadrajın bilmesi gereken pay farklı (yerinde dans: baş yükselir)."""
    plan, designs = make_project(tmp_path, name, ["Bugün hava güzel."])
    root = tmp_path / name
    a, b = [c[0] for c in sorted(PROJECTS[name][:2], key=lambda c: -c[3])]       # odak: uzun olan (üst beden kadrajı)

    def row(t0, kind, camera):
        return {"t_start": t0, "t_end": t0 + 4, "characters": [a, b], "camera": camera, "location": "yer", "action": "Durur.", "scene_id": "S",
                "choreo": {"motion": {a: {"kind": kind, "x0": -1.0}, b: {"kind": "idle", "x0": 1.2}}}}
    sheet = {"beats": [row(0, "idle", "yakın"), row(4, second, camera_b)]}
    for i, obs in (objects or {}).items():
        sheet["beats"][i]["choreo"]["objects"] = obs(a)
    (root / "ep" / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    (root / "ep" / "voice_manifest.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}

    def planned(t0=0, t1=8):
        out = sp.plan(str(root / "ep"), bible, str(root / "assets"), t0, t1)
        for pb in out["beats"] + out["context"]:
            pb["focus"] = a
        return out
    return planned, designs, a


def per_beat_run(plan, beat, lt, key):
    """Bozma: eski davranış (kadraj ihtiyacı vuruşun tamamından, her vuruşta ayrı)."""
    return [(beat, 0.0, beat["t_end"] - beat["t_start"])]


def cam_at(plan, designs, t):
    tr = {}
    r2.frame(plan, designs, t, trace=tr, camera_only=True)
    return tr


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_close_shot_across_a_beat_boundary_has_one_framing_and_per_beat_framing_is_caught(tmp_path, name, monkeypatch):
    planned, designs, _a = close_chain(tmp_path, name)
    plan = planned()
    assert plan["beats"][1]["cut_in"] and cam_at(plan, designs, 3.9)["preset"] == cam_at(plan, designs, 4.1)["preset"] == "close"
    assert readability.camera_pop_problems(readability.camera_pops(plan, designs)) == []
    monkeypatch.setattr(r2, "close_run", per_beat_run)               # bozma: vuruş başına kadraj sınırda atlar
    assert [p for p in readability.camera_pops(plan, designs) if p["kind"] == "edit" and abs(p["t"] - 4.0) < 0.1]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_chunk_edge_keeps_the_framing_of_the_shot_that_crosses_it(tmp_path, name):
    planned, designs, _a = close_chain(tmp_path, name)
    whole = planned()
    for t0, t1, t in ((0, 4, 3.5), (4, 8, 4.5)):                         # iki yönde de pencere kenarı
        part = planned(t0, t1)
        assert len(part["beats"]) == 1 and part["context"]
        want, got = cam_at(whole, designs, t)["cam"], cam_at(part, designs, t)["cam"]
        assert (got.cx, got.cy, got.s) == pytest.approx((want.cx, want.cy, want.s))
    lone = dict(planned(0, 4), context=[])                          # bozma: komşu verisi yoksa parça farklı kadraj çizer
    assert cam_at(lone, designs, 3.5)["cam"].s != pytest.approx(cam_at(whole, designs, 3.5)["cam"].s, rel=0.005)


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_hold_outside_the_close_shot_does_not_open_it_and_per_beat_framing_is_caught(tmp_path, name, monkeypatch):
    """Y2c: aynı vuruşun SONRAKİ planındaki alçak tutuş, önceki yakın planı genişletmez."""
    planned, designs, a = close_chain(tmp_path, name, second="idle", camera_b="geniş")
    sheet_path = tmp_path / name / "ep" / "beat_sheet.json"
    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
    one = sheet["beats"][0]
    one["t_end"] = 8                                                     # tek uzun vuruş: 0-3.5 yakın, sonrası başka plan
    sheet["beats"] = [one]

    def head_share(track_start):
        """1.5 sn yakın plandaki (kip, oyuncu boyu / kare yüksekliği); kürek track_start'tan sonra elde."""
        track = [{"t": 0, "holder": a}] if track_start == 0.0 else [{"t": 0, "at": [-1.4, 0.0]}, {"t": track_start, "at": [-1.4, 0.0]}, {"t": track_start + 0.6, "holder": a}] if track_start else []
        one["choreo"]["objects"] = [{"prop": "shovel", "track": track + [{"t": 8.0, "holder": a}]}] if track else []
        sheet_path.write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
        tr = cam_at(planned(), designs, 1.5)
        assert tr["preset"] == "close"
        return tr["crop"], designs[a]["height"] * tr["cam"].s / pp.H

    free = head_share(None)
    assert cam_at(planned(), designs, 5.0)["preset"] != "close"
    assert head_share(5.5)[1] == pytest.approx(free[1])                  # sonraki plandaki tutuş yakın planı etkilemez
    assert head_share(0.0)[1] < free[1] - 0.05                            # tutuş çekimin İÇİNDEYSE kadraj açılır
    monkeypatch.setattr(r2, "close_run", per_beat_run)                   # bozma: eski, vuruşun tamamına bakan kadraj
    assert head_share(5.5)[1] < free[1] - 0.05


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_edit_boundary_hidden_under_a_listener_shot_does_not_restart_the_push(tmp_path, name, monkeypatch):
    """Tepki planı sürerken alttaki kurgu listesi 3,5 sn'de çekim değiştirir: aynı yüzdeki yaklaşma başa dönmez."""
    planned, designs, a = close_chain(tmp_path, name, second="idle", camera_b="geniş")
    plan = dict(planned(), context=[])
    beat = plan["beats"][0]
    other = next(c for c in beat["cast"] if c != a)
    beat.update(t_end=8.0, camera="close", lines=[line(other, 0.4, 2.9)])
    plan["beats"] = [beat]
    assert lr.target(beat, 3.4) == lr.target(beat, 3.6) == a
    assert readability.camera_pop_problems(readability.camera_pops(plan, designs)) == []
    monkeypatch.setattr(r2, "run_phase", lambda run, b, lt: r2.shot_cuts.at(b, lt)[1])     # bozma: yaklaşma kurgu listesinden
    assert [p for p in readability.camera_pops(plan, designs) if p["kind"] == "edit" and abs(p["t"] - 3.5) < 0.1]
