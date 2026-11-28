"""Ağız, kapalı göz ve burun çizgisi her ten renginde seçilir. Ölçü çizilen pikselin PARLAKLIK farkından (tools/face_visibility.measure_lines).
Yalnız sentetik tasarımlar."""
import os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import face_visibility as fv  # noqa: E402
import puppet2d as pp  # noqa: E402

SKINS = {"acik": (1.0, 0.87, 0.75), "esmer": (0.62, 0.44, 0.30), "koyu": (0.42, 0.28, 0.19), "cok_koyu": (0.27, 0.18, 0.13)}
KIDS = {"kucuk": (3, 0.98, "kız"), "yetiskin": (35, 1.9, "erkek")}
VIEWS = tuple(v for v in fv.VIEWS if v[0] in ("front", "three_quarter_r", "side_r", "side_l"))
STATES = (("neutral", "X", 0), ("neutral", "X", 1), ("laugh", "X", 0), ("sad", "X", 0), ("angry", "A", 0), ("sly", "X", 0),
          ("neutral", "D", 0), ("neutral", "F", 0))


def design(who, skin, nose="line"):
    age, h, role = KIDS[who]
    return pp.derive_design({"id": f"s_{who}", "age": age, "role": role}, {"height_m": h, "nose": nose, "palette": {"skin": skin}})


def bad_rows(des, states=STATES, views=VIEWS):
    out = []
    for e, mouth, blink in states:
        for v in views:
            why = fv.line_failures(fv.measure_lines(des, e, v, mouth, blink))
            if why:
                out.append((e, mouth, blink, v[0], why))
    return out


@pytest.mark.parametrize("who", sorted(KIDS))
@pytest.mark.parametrize("skin", sorted(SKINS))
def test_mouth_lids_and_nose_readable_on_every_skin_tone(who, skin):
    bad = bad_rows(design(who, SKINS[skin]))
    assert not bad, bad[:4]


@pytest.mark.parametrize("nose", ["dot", "button", "round", "long"])
@pytest.mark.parametrize("skin", sorted(SKINS))
def test_every_nose_type_readable(nose, skin):
    bad = bad_rows(design("kucuk", SKINS[skin], nose), states=(("neutral", "X", 0),))
    assert not bad, bad[:4]


def test_light_skin_keeps_the_designed_ink():
    """Açık tende görünüm değişmez: çizgi rengi eskisiyle aynı."""
    skin = (255, 214, 170)
    assert pp.face_line(skin, pp.INK) == pp.INK
    assert pp.face_line(skin, pp.shade(skin, 0.62)) == pp.shade(skin, 0.62)


# ---------------------------------------------------------------- bilerek eklenen hata: eski davranış (çizgi rengi tene bakmaz)
@pytest.mark.parametrize("item,state", [("mouth", ("neutral", "X", 0)), ("lids", ("neutral", "X", 1)), ("nose", ("neutral", "X", 0))])
def test_fixed_ink_on_very_dark_skin_is_caught(monkeypatch, item, state):
    monkeypatch.setattr(pp, "face_line", lambda skin, base: base)
    why = fv.line_failures(fv.measure_lines(design("kucuk", SKINS["cok_koyu"]), state[0], fv.VIEWS[0], state[1], state[2]))
    assert any(w.startswith(item) for w in why), why


@pytest.mark.parametrize("item", ["mouth", "nose"])
def test_line_painted_in_skin_colour_is_caught_on_light_skin(monkeypatch, item):
    monkeypatch.setattr(pp, "face_line", lambda skin, base: skin)
    why = fv.line_failures(fv.measure_lines(design("yetiskin", SKINS["acik"]), "neutral", fv.VIEWS[0]))
    assert any(w.startswith(item) for w in why), why


def test_gate_reports_melted_lines(monkeypatch):
    des = design("kucuk", SKINS["cok_koyu"])
    assert not fv.problems(fv.check_designs({"k": des}, {"k"}))
    monkeypatch.setattr(pp, "face_line", lambda skin, base: base)
    found = fv.problems(fv.check_designs({"k": des}, {"k"}))
    assert found and found[0]["rule"] == "FACE_UNREADABLE", found
