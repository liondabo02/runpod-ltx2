"""Atış kolu (hazırlık, savurma, takip): omuz-dirsek-el yolu sürekli, el bıraktıktan sonra göğse dönmüyor, dirsek gövdenin içine katlanmıyor.
Ölçü çizimle aynı eklem geometrisinden (puppet2d.arm_joints); yalnız sentetik projeler. Piksel ölçüsü değildir."""
import math

import pytest

import test_throw_entry as te
import puppet2d as pp
import render2d as r2

FPS = 24
RELEASE, WINDOW = 2.0, (1.2, 3.8)       # sentetik izde bırakma anı ve ölçülen pencere (sn)
MAX_STEP = 0.60                          # bir karede dirsek/el (omuza göre) en çok bu kadar kol boyu yer değiştirir
MIN_REACH_AFTER = 0.90                   # bırakmadan sonra boş el omuza en az bu kadar uzak (göğse katlanmaz)
MAX_INWARD = 0.12                        # dirsek omuzdan gövde ortasına doğru en çok bu kadar kol boyu girebilir


def arm_path(plan, des, cid):
    """[(t, {side: (dirsek, el)})], kol boyu birimiyle, omuza göre."""
    side = r2.pick_hand(plan["beats"][0], cid)
    rows = []
    for i in range(int(WINDOW[0] * FPS), int(WINDOW[1] * FPS) + 1):
        t = i / FPS
        _c, d, p = next(it[:3] for it in r2.poses_at(plan, des, t) if it[0] == cid)
        sh, el, ha = pp.arm_joints(d, p, side)
        n = 0.27 * d["height"]
        rows.append((t, tuple(((q[0] - sh[0]) / n, (q[1] - sh[1]) / n) for q in (el, ha))))
    return side, rows


def arm_problems(plan, des, cid):
    side, rows = arm_path(plan, des, cid)
    out_sign = -1 if side == "L" else 1
    out = []
    for (t0, a), (t, b) in zip(rows, rows[1:]):
        step = max(math.dist(a[0], b[0]), math.dist(a[1], b[1]))
        if step > MAX_STEP:
            out.append(("SICRAMA", round(t, 3), round(step, 2)))
    for t, (el, ha) in rows:
        if t > RELEASE and math.hypot(*ha) < MIN_REACH_AFTER:
            out.append(("GOGSE_KIVRIK", round(t, 3), round(math.hypot(*ha), 2)))
        if el[0] * out_sign < -MAX_INWARD:
            out.append(("DIRSEK_GOVDEDE", round(t, 3), round(el[0] * out_sign, 2)))
    return out


def setup(tmp_path, name):
    plan, des = te.planned(tmp_path, name)
    return plan, des, te.CONFIGS[name][0]


@pytest.mark.parametrize("name", sorted(te.CONFIGS))
def test_throw_arm_path_is_continuous_and_clear_of_the_body(tmp_path, name):
    bad = arm_problems(*setup(tmp_path, name))
    assert not bad, bad[:6]


def test_thrown_object_no_longer_counts_as_carried_after_release(tmp_path):
    plan, _des, cid = setup(tmp_path, "yetiskin_saga")
    b = plan["beats"][0]
    assert r2.carry_info(b, cid, RELEASE - 0.1) is not None
    assert r2.carry_info(b, cid, RELEASE + 0.1) is None
    assert r2.object_effects(b, cid, RELEASE + 0.1)[1] == 0.0


def test_object_being_put_on_the_ground_is_still_carried():
    """Yere koyma bırakma değildir: el nesneyi hedefe kadar götürür."""
    beat = {"cast": ["a"], "motion": {"a": {"kind": "idle", "x0": 0.0}},
            "choreo": {"objects": [{"prop": "stone", "track": [{"t": 0, "holder": "a"}, {"t": 1.0, "holder": "a"}, {"t": 2.0, "at": [0.6, 0.0]}]}]}}
    assert r2.carry_info(beat, "a", 1.5) is not None


# ---------------------------------------------------------------- bilerek eklenen hatalar
def kinds(bad):
    return {b[0] for b in bad}


def test_hand_returning_to_carry_pose_during_flight_is_caught(tmp_path, monkeypatch):
    """Eski davranış: uçuştaki nesne hâlâ taşınıyor sayılır."""
    monkeypatch.setattr(r2, "_released", lambda *a: False)
    bad = arm_problems(*setup(tmp_path, "yetiskin_saga"))
    assert "GOGSE_KIVRIK" in kinds(bad), bad[:6]


def test_angle_only_blend_is_caught_as_a_jump(tmp_path, monkeypatch):
    """Eski davranış: yalnız açı karışır, el mesafesi tek karede değişir."""
    def angle_only(des, pose, side, tx, th, w):
        key = "a" + side; old = list(pose[key])
        pp.arm_toward(des, pose, side, tx, th)
        pose[key] = [old[0] + (pose[key][0] - old[0]) * w, old[1] + (pose[key][1] - old[1]) * w]
    monkeypatch.setattr(pp, "arm_blend", angle_only)
    bad = arm_problems(*setup(tmp_path, "yetiskin_saga"))
    assert "SICRAMA" in kinds(bad), bad[:6]


def test_elbow_folded_into_the_torso_is_caught(tmp_path, monkeypatch):
    """Eski dirsek seçimi: büküm her zaman ekranda aşağı bakan dikmeden alınır."""
    def old_elbow(sh, hand, arm_len, sg):
        dx, dy = hand[0] - sh[0], hand[1] - sh[1]; d = math.hypot(dx, dy) or 1e-6
        half = arm_len / 2.0; hgt = math.sqrt(max(0.0, half * half - (d / 2.0) ** 2))
        nx, ny = -dy / d, dx / d
        if ny < 0:
            nx, ny = -nx, -ny
        if nx * sg < 0 and abs(ny) < 0.3:
            nx, ny = -nx, -ny
        return ((sh[0] + hand[0]) / 2 + nx * hgt, (sh[1] + hand[1]) / 2 + ny * hgt)
    monkeypatch.setattr(pp, "_elbow", old_elbow)
    bad = arm_problems(*setup(tmp_path, "yetiskin_saga"))
    assert "DIRSEK_GOVDEDE" in kinds(bad), bad[:6]


@pytest.mark.parametrize("sg", [1, -1])
def test_elbow_never_switches_side_between_adjacent_directions(sg):
    prev, worst = None, 0.0
    for i in range(-400, 3100, 2):
        a = i / 1000
        e = pp._elbow((0.0, 0.0), (sg * math.sin(a) * 0.6, math.cos(a) * 0.6), 1.0, sg)
        if prev:
            worst = max(worst, math.dist(e, prev))
        prev = e
    assert worst < 0.01
