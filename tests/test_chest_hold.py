"""H13: göğüste tutulan hafif nesne yüze/ağza dayanmaz ('su içiyor' okunmaz). Sentetik gövdeler; proje dosyası okunmaz."""
import os
import sys

import pytest
from PIL import ImageChops

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import props2d  # noqa: E402
import puppet2d as pp  # noqa: E402
import readability as rd  # noqa: E402
import render2d as r2  # noqa: E402
import scenes2d as sc  # noqa: E402

BODIES = [(1.9, 40), (1.6, 70), (1.25, 8), (0.98, 6)]


def holder(height, age, prop, gaze=False):
    """Tek oyuncu, elinde nesne, yerinde duruyor; isteğe bağlı olarak yanındakine bakıyor."""
    ids = ["tutan", "diger"]
    designs = {c: pp.derive_design({"id": c, "age": age}, {"height_m": height}) for c in ids}
    motion = {"tutan": {"kind": "idle", "x0": 0.0, "x1": 0.0, "seed": 0}, "diger": {"kind": "idle", "x0": 1.4, "x1": 1.4, "seed": 1}}
    beat = {"i": 0, "t_start": 0.0, "t_end": 8.0, "cast": ids, "motion": motion, "lines": [], "camera": "wide", "focus": "tutan", "targets": {},
            "scene": "garden", "choreo": {"objects": [{"prop": prop, "track": [{"t": 0, "holder": "tutan"}, {"t": 8, "holder": "tutan"}]}],
                                          "gaze": {"tutan": "diger"} if gaze else {}, "react": {}, "points": []}}
    return {"fps": 12, "t0": 0.0, "t1": 8.0, "beats": [beat], "width": 1280, "height": 720}, designs


def face_overlap(plan, designs, t):
    """Nesnenin çizilen piksellerinin yüzde kaçı tutanın baş elipsinin içinde."""
    items = r2.poses_at(plan, designs, t)
    beat = plan["beats"][0]
    ob, x, y, _st, owner, _hand = r2._objects_now(beat, items, t)[0]
    assert owner == "tutan"
    _cid, des, pose = next((i[0], i[1], i[2]) for i in items if i[0] == "tutan")
    cam = sc.Cam(0.0, 1.0, 1.4)
    prop = rd._mask(lambda cv, cm: props2d.draw(cv, cm, ob["prop"], x, y, t, 0, scale=ob.get("scale", 0.55)), cam)
    cx, cy, rx, ry = pp.face_ellipse(des, pose)
    face = rd._mask(lambda cv, cm: cv.ellipse(cm.x(pose["x"] + cx), cm.y(cy), rx * cm.s, ry * cm.s, (255, 255, 255), None, 0), cam)
    assert rd._count(prop) > 100
    return rd._count(ImageChops.multiply(prop, face)) / rd._count(prop)


TIMES = [0.6, 1.7, 3.1, 4.4, 6.3]


@pytest.mark.parametrize("height,age", BODIES)
@pytest.mark.parametrize("prop", ["bottle", "lantern", "seed", "stone", "hat"])
@pytest.mark.parametrize("gaze", [False, True])
def test_held_light_prop_stays_off_the_face(height, age, prop, gaze):
    plan, designs = holder(height, age, prop, gaze)
    worst = max(face_overlap(plan, designs, t) for t in TIMES)
    assert worst <= 0.005, worst


@pytest.mark.parametrize("height,age", BODIES)
def test_measure_catches_the_old_chest_height(monkeypatch, height, age):
    """Bilerek bozma: eski kural (yüze bakmadan omzun 0,2 kol boyu altı) yüze biner ve ölçü bunu görür."""
    plan, designs = holder(height, age, "bottle")
    monkeypatch.setattr(r2, "chest_hold_height", lambda des, pose, dx, shoulder_h, prop, scale: shoulder_h - 0.20 * des["height"] * 0.27)
    assert max(face_overlap(plan, designs, t) for t in TIMES) > 0.02


@pytest.mark.parametrize("height,age", BODIES)
def test_hand_does_not_drop_to_the_hip(height, age):
    """Yüzden kaçarken tutuş 'kalçada sallanan nesne'ye dönmez."""
    for prop in ("bottle", "lantern", "flower", "balloon", "kite"):
        plan, designs = holder(height, age, prop)
        items = r2.poses_at(plan, designs, 3.0)
        _c, des, pose = items[0][0], items[0][1], items[0][2]
        side = r2.pick_hand(plan["beats"][0], "tutan")
        drop = pp.shoulder_offset(des, pose, side)[1] - pp.hand_offset(des, pose, side)[1]
        assert drop <= (r2.CHEST_HOLD_FLOOR_K + 0.05) * des["height"] * 0.27, (prop, drop)
