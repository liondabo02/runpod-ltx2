"""Q10: sahne sözleşmesi ile ses işçisi/diyalog kapısı aynı replik listesini okur. İki farklı sentetik proje."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import dialogue_check as dc  # noqa: E402
import scene_contract as sc  # noqa: E402

PROJECTS = {
    "deniz": {"chars": {"kaptan": {"id": "kaptan", "name": "Kaptan Ada"}, "mico": {"id": "mico", "name": "Miço"}},
              "a": "kaptan", "b": "mico", "an": "Kaptan Ada", "bn": "Miço", "t": ["Feneri gördün mü?", "Evet, orada!", "Haydi gidelim."]},
    "garden": {"chars": {"robin": {"id": "robin", "name": "Robin"}, "sam": {"id": "sam", "name": "Uncle Sam"}},
               "a": "robin", "b": "sam", "an": "Robin", "bn": "Uncle Sam", "t": ["Is that the shovel?", "Yes: take it.", "Let's dig."]},
}


def forms(p):
    a, b, t = p["a"], p["b"], p["t"]
    return {"cizgi_kimlik": f"{a}: {t[0]} | {b}: {t[1]} | {a}: {t[2]}",
            "satir_ici_ad": f"{p['an']}: {t[0]} {p['bn']}: {t[1]} {p['an']}: {t[2]}",
            "satir_sonu": f"{p['an']}: {t[0]}\n{b}: {t[1]}\n{a}: {t[2]}"}


def contract(p, dialogue, lines=None):
    cast = [p["a"], p["b"]]
    sheet = {"beats": [{"t_start": 0, "t_end": 9, "scene_id": "S", "shot_id": "s1", "location": "yer", "characters": cast, "dialogue": dialogue}]}
    plan = {"beats": [{"i": 0, "cast": cast, "motion": {c: {"x0": i, "x1": i} for i, c in enumerate(cast)}, "lines": lines or []}]}
    c = sc.from_beat_sheet(sheet, plan, project_id="x", episode_id="e", characters=p["chars"])
    return sheet, [e for e in c["shots"][0]["events"] if e["kind"] == "dialogue"]


@pytest.mark.parametrize("name", sorted(PROJECTS))
@pytest.mark.parametrize("form", ["cizgi_kimlik", "satir_ici_ad", "satir_sonu"])
def test_contract_reads_the_same_lines_as_the_voice_side(name, form):
    p = PROJECTS[name]
    sheet, events = contract(p, forms(p)[form])
    bible = {"characters": list(p["chars"].values())}
    expected = dc.expected_lines(sheet, bible)[0][0]
    assert [(e["char"], e["text"]) for e in events] == expected == [(p["a"], p["t"][0]), (p["b"], p["t"][1]), (p["a"], p["t"][2])]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_second_line_of_the_same_speaker_gets_its_own_timing(name):
    p = PROJECTS[name]
    lines = [{"char": p["a"], "start": 0.2, "end": 1.5}, {"char": p["b"], "start": 1.8, "end": 3.0}, {"char": p["a"], "start": 3.3, "end": 4.4}]
    _s, events = contract(p, forms(p)["cizgi_kimlik"], lines)
    assert [(e["t_start"], e["t_end"]) for e in events] == [(0.2, 1.5), (1.8, 3.0), (3.3, 4.4)]
    _s, short = contract(p, forms(p)["cizgi_kimlik"], lines[:2])                       # ses listesinde eksik satır: zaman uydurulmaz
    assert short[2]["t_start"] is None
