"""Geniş ve orta planda en uzun oyuncunun başı üstten kesilmez. Ölçü gerçek kare yolunun kamerasından. Yalnız sentetik proje."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import render2d as r2  # noqa: E402
import scenes2d as sc  # noqa: E402
import shot_planner as sp  # noqa: E402


def project(tmp_path, tall, camera, partner=True):
    root = tmp_path / "p"; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    chars = [{"id": "uzun", "name": "uzun", "age": 40, "role": "erkek"}, {"id": "kisa", "name": "kisa", "age": 4, "role": "kız"}]
    cast = ["uzun", "kisa"] if partner else ["uzun"]
    bible = {"id": "p", "characters": chars}
    for c, h in (("uzun", tall), ("kisa", 0.98)):
        json.dump({"height_m": h}, open(root / "assets" / f"{c}.spec.json", "w"))
    json.dump({}, open(root / "locations.json", "w")); json.dump(bible, open(root / "series-bible.json", "w"))
    motion = {c: {"kind": "idle", "x0": -0.6 + 1.2 * i} for i, c in enumerate(cast)}
    beat = {"t_start": 0, "t_end": 4, "scene_id": "S1", "shot_id": "p1", "location": "", "characters": cast, "action": "", "camera": camera,
            "choreo": {"motion": motion}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return sp.plan(str(ep), bible, str(root / "assets"), 0, 4), pp.designs_for(bible, str(root / "assets"))


def head_tops(plan, designs):
    """Geniş/orta çıkan her karede en uzun oyuncunun baş tepesinin ve zeminin ekran y'si."""
    out = []
    for i in range(16):
        tr = {}
        r2.frame(plan, designs, i / 4, trace=tr)
        if tr["preset"] in ("wide", "medium"):
            out.append((tr["cam"].y(max(designs[c]["height"] for c in tr["beat"]["cast"]) * r2.HEAD_TOP_K), tr["cam"].y(0.0)))
    return out


@pytest.mark.parametrize("partner", [True, False])
@pytest.mark.parametrize("camera", ["geniş plan", "orta plan"])
@pytest.mark.parametrize("tall", [1.9, 2.3, 2.9])
def test_tallest_head_and_the_ground_stay_in_frame(tmp_path, tall, camera, partner):
    rows = head_tops(*project(tmp_path, tall, camera, partner))
    assert rows
    assert all(top >= r2.HEAD_MARGIN_PX - 0.5 and ground <= r2.FEET_MAX_PX + 0.5 for top, ground in rows), rows


def test_framing_that_already_fits_is_unchanged():
    assert r2.head_safe_framing(0.95, 1.0, 1.7, sc.BASE_PPM) == (0.95, 1.0)


def test_old_framing_cuts_a_tall_head(tmp_path, monkeypatch):
    monkeypatch.setattr(r2, "head_safe_framing", lambda cy, zoom, tallest, ppm: (cy, zoom))
    rows = head_tops(*project(tmp_path, 2.3, "orta plan"))
    assert any(top < 0 for top, _g in rows), rows
