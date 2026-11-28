"""Profil yüz: ifade okunur (tepki planı profil dinleyicide de çalışır), burun göze binmez, şaşkın yüzde ağız açıktır.
Tasarımlar sentetik; proje verisi kodda sabit değil."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import face_visibility as fv  # noqa: E402
import listener_reaction as lr  # noqa: E402
import puppet2d as pp  # noqa: E402
import puppet_side  # noqa: E402
import readability  # noqa: E402
import render2d as r2  # noqa: E402

CHARS = [("mino", "kız çocuk", 4, 0.98), ("dede_x", "dede (erkek)", 62, 1.9), ("lale", "anne (kadın)", 35, 1.68),
         ("orhan", "baba", 40, 1.82), ("bebek_x", "bebek", 1, 0.7), ("kirpi_x", "kirpi", 3, 0.6), ("kuz", "küçük oğlan", 3, 0.9)]
SIDES = (("side_r", 0.9, 0.0), ("side_l", -0.9, 0.0))
MOODS = sorted(set(lr.RESPONSE.values()))                       # tepki motorunun dinleyiciye verebildiği her ifade


@pytest.fixture(scope="module")
def designs(tmp_path_factory):
    root = tmp_path_factory.mktemp("assets")
    for cid, _r, _a, h in CHARS:
        (root / f"{cid}.spec.json").write_text(json.dumps({"height_m": h}), encoding="utf-8")
    return pp.designs_for({"characters": [{"id": c, "name": c.title(), "role": r, "age": a} for c, r, a, _h in CHARS]}, str(root))


class _Cam:
    def __init__(self, des, head_px=240):
        self.s = head_px / (des["height"] * pp.head_share(des))
        self.floor = 140 + self.s * des["height"]               # baş tuvalin içinde kalır

    def x(self, v):
        return readability.W / 2 + v * self.s

    def y(self, v):
        return self.floor - v * self.s


def reaction_change(des, view, mood):
    """Tepki kapısının kullandığı ölçünün aynısı (readability.face_change), tepki oyunculuğunun verdiği kaş ve bakışla."""
    toward = 0.9 if view[1] > 0 else -0.9
    st = {"mouth": "X", "blink": False, "eyes_open": True, "emotion": mood, "gaze": toward, "brow": lr.BROW, "pulse": 0.0}
    return readability.face_change(des, fv.pose(*view), st, _Cam(des))


@pytest.mark.parametrize("view", SIDES, ids=lambda v: v[0])
@pytest.mark.parametrize("mood", MOODS)
def test_profile_expression_passes_the_reaction_gate_with_margin(designs, view, mood):
    values = {c: reaction_change(d, view, mood) for c, d in designs.items()}
    need = 1.5 * readability.DEFAULTS["react_face_min"]                        # kapı eşiği gevşetilmedi; pay ayrıca istenir
    assert min(values.values()) >= need, values


def test_the_measure_still_rejects_a_blank_profile_face(designs):
    for d in designs.values():
        st = {"mouth": "X", "blink": False, "eyes_open": True, "emotion": "neutral", "gaze": 0.0, "brow": 0.0, "pulse": 0.0}
        assert readability.face_change(d, fv.pose(*SIDES[0]), st, _Cam(d)) < readability.DEFAULTS["react_face_min"]


@pytest.mark.parametrize("view", SIDES, ids=lambda v: v[0])
def test_nose_never_covers_the_eye_in_profile(designs, view):
    assert {(c, e): n for c, d in designs.items() for e in fv.EMOTIONS for n in (fv.nose_over_eye(d, e, view),) if n} == {}


def test_gate_catches_a_nose_drawn_over_the_eye(designs, monkeypatch):
    monkeypatch.setattr(puppet_side, "NOSE_U", 0.36)
    monkeypatch.setattr(puppet_side, "NOSE_V", 0.04)
    report = fv.check_designs(designs, ["mino"])
    assert any("burun göze biniyor" in w for f in report["mino"]["fails"] for w in f["why"]), report


@pytest.mark.parametrize("view", SIDES, ids=lambda v: v[0])
def test_profile_eyes_brows_and_mouth_stay_readable_for_every_emotion(designs, view):
    bad = {}
    for c, d in designs.items():
        for e in fv.EMOTIONS:
            why = fv.failures(fv.measure(d, e, view)) + fv.line_failures(fv.measure_lines(d, e, view))
            if why:
                bad[(c, e)] = why
    assert bad == {}


# ---------------------------------------------------------------- konuşmayan şaşkın yüz
def _mouth_open_px(des, view, emotion):
    """Dinlenen ağzın içindeki koyu dolgu pikselleri (kapalı çizgi ağızda ~0)."""
    p = fv.pose(*view)
    st = {"mouth": "X", "blink": 0, "emotion": emotion, "gaze": 0.0, "brow": 0.0, "pulse": 0.0}
    mask = fv._changed(fv.render(des, p, st), fv.render(des, p, dict(st, hide=("mouth",))))
    img = fv.render(des, p, st).convert("RGB")
    return sum(1 for m, (r, g, b) in zip(mask.tobytes(), zip(*[c.tobytes() for c in img.split()])) if m and 90 <= r <= 135 and g <= 45 and 30 <= b <= 60)


@pytest.mark.parametrize("view", (("front", 0.0, 0.0),) + SIDES, ids=lambda v: v[0])
def test_surprised_resting_mouth_is_open(designs, view):
    for c in ("mino", "dede_x"):
        assert _mouth_open_px(designs[c], view, "surprise") >= 60, c
        assert _mouth_open_px(designs[c], view, "happy") == 0, c


def test_open_mouth_measure_catches_the_closed_smile(designs, monkeypatch):
    monkeypatch.setattr(pp, "REST_O_RX", 0.0)
    monkeypatch.setattr(pp, "REST_O_RY", 0.0)
    assert _mouth_open_px(designs["mino"], ("front", 0.0, 0.0), "surprise") < 60


# ---------------------------------------------------------------- uçtan çizim yolu: koşan (profil) dinleyiciye kesen plan
@pytest.mark.parametrize("name", ("kisa_uzun", "iki_yetiskin"))
def test_profile_listener_reaction_shot_passes_the_render_gate(tmp_path, name):
    from test_listener_reaction import PROJECTS, make_project
    a, b = PROJECTS[name][0][0], PROJECTS[name][1][0]
    plan, des = make_project(tmp_path, name, ["Bugün hava güzel.", "Aferin sana!", "Nerede kaldı acaba?"],
                             motion={a: {"kind": "run", "x0": -2.6, "x1": -0.8}, b: {"kind": "run", "x0": 2.6, "x1": 0.8}})
    shots = readability.reaction_shots(plan, des)
    views = []
    for s in shots:
        tr = {}
        r2.frame(plan, des, s["sample_t"], trace=tr)
        views.append(pp.view_of({i[0]: i for i in tr["items"]}[s["listener"]][2]))
    assert "side" in views, (views, shots)                       # sınanan durum gerçekten profil
    assert readability.reaction_problems(shots) == [], list(zip(views, shots))


# ---------------------------------------------------------------- gülen göz: alt kenar kapak çizgisiyle kapanır (ön, üç-çeyrek, profil)
@pytest.mark.parametrize("view", (("front", 0.0, 0.0), ("three_quarter_l", -0.55, 0.0)) + SIDES, ids=lambda v: v[0])
@pytest.mark.parametrize("emotion", ("happy", "laugh"))
def test_smiling_eye_is_closed_by_a_lid_line(designs, view, emotion):
    values = {c: round(fv.lower_lid_lined(d, view, emotion), 3) for c, d in designs.items()}
    assert min(values.values()) >= 0.97, values


def test_lid_measure_catches_an_eye_cut_without_a_line(designs, monkeypatch):
    real = pp.Cv.poly

    def unlined(self, pts, fill, ol=None, ow=3.0):
        return real(self, pts, fill, None if fill == (255, 255, 255) else ol, ow)       # göz akı dış çizgisiz kesilir
    monkeypatch.setattr(pp.Cv, "poly", unlined)
    monkeypatch.setattr(pp, "LID_LINE_K", 0.01)
    assert fv.lower_lid_lined(designs["mino"], ("front", 0.0, 0.0), "happy") < 0.9


# ---------------------------------------------------------------- profil kaşı başın dışına (gökyüzüne) taşmaz
def _brow_outside_px(des, view, emotion):
    p = fv.pose(*view)
    st = {"mouth": "X", "blink": 0, "emotion": emotion, "gaze": 0.0, "brow": lr.BROW, "pulse": 0.0}
    without = fv.render(des, p, dict(st, hide=("brows",))).convert("RGB")
    mask = fv._changed(fv.render(des, p, st), without)
    sky = without.getpixel((2, 2))
    return sum(1 for m, c in zip(mask.tobytes(), zip(*[ch.tobytes() for ch in without.split()])) if m and c == sky)


@pytest.mark.parametrize("view", SIDES, ids=lambda v: v[0])
def test_profile_brow_stays_on_the_head(designs, view):
    bad = {(c, e): n for c, d in designs.items() for e in fv.EMOTIONS for n in (_brow_outside_px(d, view, e),) if n > 12}
    assert bad == {}


def test_sky_measure_catches_a_floating_brow(designs, monkeypatch):
    """Bilerek bozma: başın içinde tutma kapatılır ve kaş yukarı itilir."""
    monkeypatch.setattr(puppet_side, "_inside_head", lambda pts, hx, cy, rx, ry, d: [(x, y - 0.12 * ry) for x, y in pts])
    assert _brow_outside_px(designs["mino"], SIDES[0], "surprise") > 12
