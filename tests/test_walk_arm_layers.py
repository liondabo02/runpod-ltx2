"""Üç-çeyrek yürüyüşte uzak kol gövdenin ARKASINDA, yakın kol ÖNÜNDE çizilir. Ölçü gerçek çizim yolunun pikselinden: uzak ön kol ve el gövdeyle
kesiştiği alanda görünmez, yakın elin merkezi her karede görünür. Tutan / uzanan / taşıyan / jest yapan kol arkaya geçmez
(tutulan nesnenin katmanı değişmez). Yalnız sentetik değerler."""
import os, sys

import pytest
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import shot_motion as sm  # noqa: E402

FPS = 24
SKIN = (10, 200, 250)      # başka hiçbir öğede olmayan renk
MIN_OVERLAP = 0.15         # uzak ön kol + el bölgesinin gövdeyle en az bu kadarı kesişen kare ölçülür
MAX_LEAK = 0.05            # kesişen alanda görünen el (ten) pikseli en çok bu oranda
CAST = {"child": (4, 0.98, None), "adult": (35, 1.9, None), "skirt": (33, 1.7, "skirt")}
ROUTES = [(-1.0, 1.0, 4.0), (1.2, -0.8, 4.0)]      # sağa ve sola


def design(name):
    age, h, lower = CAST[name]
    d = pp.derive_design({"id": f"s_{name}", "age": age, "role": "erkek"}, {"height_m": h})
    d["skin"] = SKIN
    if lower:
        d["lowerwear"] = lower
    return d


def hand_visibility(des, route, monkeypatch, step=2):
    """Üç-çeyrek yürüyüş karelerinde: (uzak el gövde içindeyken görünen kare, uzak el gövde içindeki kare, yakın eli görünmeyen kare, toplam).
    Uzak/yakın taraf burada ölçünün KENDİ bilgisinden gelir (gidiş yönü), motorun far_arm kararından değil."""
    x0, x1, dur = route
    pos, torso = {}, []
    real_hand, real_cel = pp._hand, pp.Cv.poly_cel

    def spy_hand(cv, p, r, skin, sg, *a, **k):
        pos["L" if sg < 0 else "R"] = (p, r)
        real_hand(cv, p, r, skin, sg, *a, **k)

    def spy_cel(self, pts, *a, **k):
        torso.append(list(pts))
        real_cel(self, pts, *a, **k)

    monkeypatch.setattr(pp, "_hand", spy_hand)
    monkeypatch.setattr(pp.Cv, "poly_cel", spy_cel)
    far = "R" if x1 > x0 else "L"
    near = "L" if far == "R" else "R"
    leak = inside = lost = total = 0
    for i in range(0, int(dur * FPS) + 1, step):
        p = sm.pose_at("walk", i / FPS, dur, 1, x0, x1, des["height"], 0.0)
        if pp.view_of(p) != "three_quarter":
            continue
        pos.clear(); torso.clear()
        cv = pp.Cv(500, 600, ss=1)
        pp.draw_character(cv, des, p, {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0}, 250, 560, 220.0, 0.0)
        img = cv.img.convert("RGB")

        def skin_at(pt):
            return img.getpixel((int(round(pt[0])), int(round(pt[1])))) == SKIN

        total += 1
        lost += not skin_at(pos[near][0])
        w, h = img.size
        body = Image.new("L", (w, h), 0)
        ImageDraw.Draw(body).polygon(torso[0], fill=255)          # ilk gölgeli çokgen gövdedir
        body = body.filter(ImageFilter.MinFilter(7))              # gövde dış çizgisi sayılmaz
        (hx, hy), r = pos[far]
        sdx, sh_h = pp.shoulder_offset(des, p, far)
        sx, sy = 250 + sdx * 220.0, 560 - sh_h * 220.0
        arm = Image.new("L", (w, h), 0)                           # ön kol (omuz-el yolunun alt yarısı) + el
        d_ = ImageDraw.Draw(arm)
        d_.line([((sx + hx) / 2, (sy + hy) / 2), (hx, hy)], fill=255, width=max(3, int(r * 0.9)))
        d_.ellipse([hx - r * 0.8, hy - r * 0.8, hx + r * 0.8, hy + r * 0.8], fill=255)
        box = arm.getbbox()
        over = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2]) if body.getpixel((x, y)) and arm.getpixel((x, y))]
        full = sum(1 for v in arm.getdata() if v)
        if len(over) >= full * MIN_OVERLAP:
            inside += 1
            leak += sum(img.getpixel(q) == SKIN for q in over) > len(over) * MAX_LEAK
    return leak, inside, lost, total


@pytest.mark.parametrize("name", sorted(CAST))
@pytest.mark.parametrize("route", ROUTES, ids=["right", "left"])
def test_far_hand_passes_behind_the_torso_and_near_hand_stays_in_front(name, route, monkeypatch):
    leak, inside, lost, total = hand_visibility(design(name), route, monkeypatch)
    assert total >= 20 and inside >= 5, (inside, total)
    assert leak == 0 and lost == 0, (leak, inside, lost, total)


@pytest.mark.parametrize("name", sorted(CAST))
def test_both_arms_in_front_is_caught(name, monkeypatch):
    """Bilerek eski davranış: iki kol da gövdenin önünde; ölçü yakalar."""
    monkeypatch.setattr(pp, "far_arm", lambda pose: None)
    leak, inside, _lost, _total = hand_visibility(design(name), ROUTES[0], monkeypatch)
    assert inside >= 5 and leak >= inside * 0.8, (leak, inside)


@pytest.mark.parametrize("name", sorted(CAST))
def test_wrong_arm_behind_is_caught(name, monkeypatch):
    """Bilerek ters katman: yakın kol arkada; ölçü yakalar."""
    real = pp.far_arm
    monkeypatch.setattr(pp, "far_arm", lambda pose: {"L": "R", "R": "L", None: None}[real(pose)])
    leak, inside, lost, _total = hand_visibility(design(name), ROUTES[0], monkeypatch)
    assert leak > 0 and (lost > 0 or inside == 0), (leak, inside, lost)


def walking_pose(x0=-1.0, x1=1.0):
    return sm.pose_at("walk", 2.0, 4.0, 1, x0, x1, 1.9, 0.0)


def test_far_side_follows_the_walking_direction():
    assert pp.far_arm(walking_pose(-1.0, 1.0)) == "R"
    assert pp.far_arm(walking_pose(1.0, -1.0)) == "L"


def test_reaching_gesturing_carrying_and_standing_arms_stay_in_front():
    des = design("adult")
    base = walking_pose()
    far = pp.far_arm(base)
    reach = dict(base, aL=list(base["aL"]), aR=list(base["aR"]))
    pp.arm_blend(des, reach, far, 0.4, 1.2, 0.3)
    assert pp.far_arm(reach) is None                                  # uzanma başlar başlamaz kol öndedir
    hold = dict(base, aL=list(base["aL"]), aR=list(base["aR"]))
    pp.arm_toward(des, hold, far, 0.2, 1.2)
    assert pp.far_arm(hold) is None
    assert pp.far_arm(dict(base, hand="point", hand_side=far)) is None
    assert pp.far_arm(sm.pose_at("carry", 2.0, 4.0, 1, -1.0, 1.0, 1.9, 0.0)) is None
    assert pp.far_arm(sm.pose_at("idle", 2.0, 4.0, 1, 0.0, 0.0, 1.9, 0.0)) is None
