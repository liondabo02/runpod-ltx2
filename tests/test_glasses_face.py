"""H22: gözlüklü (yaşlı) tasarımlar yüz kapısından geçer. Dönen yüzde gözlüğün uzak camı burun çizgisinin üstüne binmez (burun camın önündedir).
Yaş / boy / cinsiyet / ten / burun biçimi taraması sentetik tasarımlarla; eşik face_visibility'den, burada gevşetilmez."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import face_visibility as fv  # noqa: E402
import puppet2d as pp  # noqa: E402

TURNS = [v for v in fv.VIEWS if not v[0].startswith("side")]
CASES = [(62, 1.75, "erkek dede", "line", (255, 214, 170)), (70, 1.6, "kadın nine", "line", (255, 214, 170)),
         (70, 1.0, "kadın nine", "dot", (92, 58, 40)), (85, 1.5, "erkek dede", "button", (92, 58, 40)),
         (85, 1.72, "kadın nine", "round", (255, 214, 170)), (66, 1.8, "erkek dede", "long", (160, 110, 75))]


def design(age, h, role, nose, skin):
    d = pp.derive_design({"id": "yasli", "name": "yasli", "role": role, "age": age}, {"height_m": h, "nose": nose, "palette": {"skin": list(skin)}})
    assert d["accessory"] == "glasses"
    return d


@pytest.mark.parametrize("age,h,role,nose,skin", CASES)
def test_nose_stays_readable_behind_glasses_when_the_face_turns(age, h, role, nose, skin):
    d = design(age, h, role, nose, skin)
    for view in TURNS:
        why = fv.line_failures(fv.measure_lines(d, "neutral", view, "X", 0))
        assert not why, (view[0], why)


def test_elderly_design_passes_the_render_face_gate():
    d = design(70, 1.6, "kadın nine", "line", (255, 214, 170))
    assert fv.problems(fv.check_designs({"nine": d}, {"nine"})) == []
