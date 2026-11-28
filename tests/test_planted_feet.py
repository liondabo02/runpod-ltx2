"""H6: yerde basılı ayak sürüklenmez. Yürüyüşü kesen tepki frenleyip iki adımda durur; bekleyen/bakınan oyuncu ayakları yerindeyken
ağırlık aktarır; bakınırken yön tek karede ters dönmez. Ölçü foot_slides (çizime giden poz), render kapısı AYAK_KAYMASI. Sentetik projeler."""
import json

import pytest

import test_pose_jumps as tp          # sys.path ayarı da buradan
import readability as rd
import render2d as r2
import render_worker
import shot_motion as sm

# (sahne adı) -> build() ayarları; iki yön, çocuk/yetişkin boyu, farklı tepki ve eylemler
SCENES = {
    "yururken_sasirma": dict(kind="walk", react="surprise", hold="bottle"),
    "tasirken_gulme": dict(kind="carry", react="laugh", hold="bottle"),
    "kosarken_sasirma": dict(kind="run", react="surprise"),
    "yetiskin_yururken_sasirma": dict(kind="walk", react="surprise", line=True, heights=(1.9, 1.7)),
    "cocuk_yururken_bakinma_tepkisi": dict(kind="walk", react="look", heights=(0.98, 1.1)),
    "bakinma_sonra_uzanma": dict(kind="look", next_kind="reach"),
    "bakinirken_sasirma": dict(kind="look", react="surprise"),
    "bekleme_replik_el_sallama": dict(kind="idle", line=True, next_kind="wave"),
    "yurume_sonra_bakinma": dict(kind="walk", next_kind="look", line=True),
}


def plan_of(tmp_path, name, **extra):
    return tp.build(tmp_path, **dict(SCENES[name], **extra))[:2]


def pose(plan, des, t, cid="a"):
    return next(i for i in r2.poses_at(plan, des, t) if i[0] == cid)[2]


@pytest.mark.parametrize("name", sorted(SCENES))
def test_planted_feet_do_not_slide(tmp_path, name):
    plan, des = plan_of(tmp_path, name)
    bad = rd.foot_slides(plan, des)
    assert not bad, bad[:6]


@pytest.mark.parametrize("name", [n for n in sorted(SCENES) if "yuru" in n or "tasirken" in n or "kosarken" in n])
def test_reaction_stops_the_walk_and_the_next_shot_starts_there(tmp_path, name):
    plan, des = plan_of(tmp_path, name)
    m, H = plan["beats"][0]["motion"]["a"], des["a"]["height"]
    if SCENES[name].get("react") is None:
        pytest.skip("tepki yok")
    th = m["halt_t"]
    at_react, stopped, later = (sm.motion_x(m, t, 6.0, H) for t in (th, th + 0.6, 5.9))
    assert stopped == pytest.approx(later, abs=1e-6)                               # durdu: tepki boyunca yol almaz
    assert abs(stopped - at_react) <= sm.STOP_MAX_K * H + 1e-6                     # fren kısa: hedefe kadar süzülmez
    own = sm.LOOK_SHIFT_K + sm.IDLE_SHIFT_K if SCENES[name]["react"] == "look" else 0.0      # bakınma tepkisinin kendi ağırlık aktarımı
    assert pose(plan, des, 5.9)["x"] == pytest.approx(later, abs=own * H + 1e-6)   # çizim = planlayıcının konumu
    assert pose(plan, des, 6.0 - 1e-4)["x"] == pytest.approx(m["x_end"], abs=1e-3)  # sonraki plan oyuncunun durduğu yerden sürer
    assert m["x_end"] == pytest.approx(sm.exit_x(m, 6.0, H, {"t": th, "kind": SCENES[name]["react"]}), abs=1e-4)
    for side in "LR":                                                              # sonunda ayaklar gövdenin altında toplanmış
        p4 = pose(plan, des, 4.0)
        assert p4["x"] + p4["f" + side] * H == pytest.approx(later, abs=1e-3) and p4["h" + side] < 1e-6


def test_second_foot_stays_down_while_first_foot_steps(tmp_path):
    """Ayaklar birden toplanmaz: önce biri basar, öbürü o sırada yerinde ve yerdedir."""
    plan, des = plan_of(tmp_path, "yururken_sasirma")
    m, H = plan["beats"][0]["motion"]["a"], des["a"]["height"]
    info = sm.halt_info(m, 6.0, H)
    second = "L" if info["first"] == "R" else "R"
    start = info["feet"][second][0]
    for k in range(10):
        assert sm.halt_feet(info, sm.STOP_STEP_S * k / 10)[second][0] == pytest.approx(start)
    end = sm.halt_feet(info, sm.STOP_STEP_S + sm.GATHER_STEP_S)
    for side in "LR":
        assert end[side] == pytest.approx((info["stop"], 0.0), abs=1e-9)
    mid = sm.halt_feet(info, sm.STOP_STEP_S + sm.GATHER_STEP_S / 2)[second]
    assert mid[1] > 0.012 * H                                                      # toplama gerçek adım: ayak kalkar


def test_reaction_after_arrival_changes_nothing(tmp_path):
    plan, des = plan_of(tmp_path, "yururken_sasirma")
    m, H = dict(plan["beats"][0]["motion"]["a"]), des["a"]["height"]
    m["halt_t"] = 5.9                                    # yürüyüş 0.85*6 = 5.1 sn'de biter
    free = {k: v for k, v in m.items() if k != "halt_t"}
    assert sm.motion_x(m, 6.0, 6.0, H) == pytest.approx(sm.motion_x(free, 6.0, 6.0, H), abs=1e-6)


@pytest.mark.parametrize("seed", range(7))
def test_looking_around_turns_without_a_one_frame_flip_and_stays_on_its_mark(seed):
    prev = None
    for i in range(int(12 * 48) + 1):
        p = sm.pose_at("look", i / 48, 12.0, seed, 0.4, 0.4, 1.2, 0.54)
        if prev is not None:
            assert abs(p["yaw"] - prev) < 0.12, (i / 48, prev, p["yaw"])
        prev = p["yaw"]
        assert abs(p["x"] - 0.4) <= (sm.LOOK_SHIFT_K + sm.IDLE_SHIFT_K) * 1.2 + 1e-9
    assert sm.pose_at("look", 12.0, 12.0, seed, 0.4, 0.4, 1.2, 0.54)["x"] == pytest.approx(0.4)


# ---------------------------------------------------------------- bilerek eklenen hatalar
def test_reaction_that_keeps_gliding_is_caught(tmp_path, monkeypatch):
    """Eski davranış: tepki pozundaki oyuncu yürüyüş yolunda süzülür."""
    monkeypatch.setattr(sm, "mark_halt", lambda motion, react: None)
    bad = rd.foot_slides(*plan_of(tmp_path, "yururken_sasirma"))
    assert any(r["actor"] == "a" and r["dist"] > 0.1 for r in bad), bad


def test_feet_that_follow_the_swaying_body_are_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(r2, "ground_feet", lambda p, *a: p)
    monkeypatch.setattr(sm, "IDLE_SHIFT_K", 0.2)
    bad = rd.foot_slides(*plan_of(tmp_path, "bakinma_sonra_uzanma"))
    assert bad, "gövdeyle sürüklenen ayak yakalanmalıydı"


def test_render_gate_blocks_sliding_feet_before_drawing(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "mark_halt", lambda motion, react: None)
    root, ep, bible = tp.build(tmp_path, **SCENES["yetiskin_yururken_sasirma"])[2:]
    monkeypatch.setattr(rd, "pose_jump_problems", lambda rows: [])        # yalnız ayak kapısı sınanır
    drawn = []
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: drawn.append(1))
    out = render_worker.run(str(ep), bible, 0, 6, str(root))
    assert out["status"] == "BLOCKED" and out["error"] == "AYAK_KAYMASI", out
    assert any("FOOT_SLIDE" in p for p in out["problems"])
    assert json.loads((ep / "render" / "foot_slides.json").read_text(encoding="utf-8"))["slides"]
    assert not drawn
