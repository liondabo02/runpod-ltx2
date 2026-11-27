"""Nesne eylemi sırasında yüz: gözler kapalı gülmez, hedefe bakar; uzun gülmede gözler dalga dalga kapanır.
Ölçü: render2d.frame'in karakter çizicisine verdiği yüz durumu (gerçek çizim yolu); ayrıca açık/kapalı gözün pikselde ayrıldığı kontrol edilir."""
import json

import pytest

import test_throw_entry as te
import face_visibility as fv
import puppet2d as pp
import render2d as r2
import shot_planner as sp

FPS = 12
LAUGH = "laugh"


def laughing_throw(tmp_path, name):
    root, ep, bible = te.project(tmp_path, name)
    sheet = json.load(open(ep / "beat_sheet.json"))
    for m in sheet["beats"][0]["choreo"]["motion"].values():
        m["kind"] = LAUGH                                               # iki oyuncu da bütün vuruş boyunca gülüyor
    json.dump(sheet, open(ep / "beat_sheet.json", "w"))
    return sp.plan(str(ep), bible, str(root / "assets"), 0, 6), pp.designs_for(bible, str(root / "assets"))


def face_states(plan, des, monkeypatch, t0=0.0, t1=6.0):
    """[(t, {kimlik: (durum, x)})]"""
    seen = {}
    real = pp.draw_character

    def spy(cv, d, pose, st, *a, **k):
        seen[d["id"]] = (dict(st), pose["x"])
        return real(cv, d, pose, st, *a, **k)
    monkeypatch.setattr(pp, "draw_character", spy)
    rows = []
    for i in range(int(t0 * FPS), int(t1 * FPS)):
        seen.clear()
        r2.frame(plan, des, i / FPS)
        rows.append((i / FPS, dict(seen)))
    return rows


def shut(st):
    return bool(st["blink"]) or (st["emotion"] == LAUGH and not st.get("eyes_open"))


def problems(rows, event_t=(2.0, 3.2), bin_x=1.0, max_shut_s=1.2):
    out, run = [], {}
    for t, cast in rows:
        for cid, (st, x) in cast.items():
            if event_t[0] - 0.4 <= t <= event_t[1] + 0.2:
                if shut(st):
                    out.append(("EYLEMDE_GOZ_KAPALI", cid, round(t, 2)))
                if st["gaze"] * (bin_x - x) <= 0:
                    out.append(("HEDEFE_BAKMIYOR", cid, round(t, 2)))
            run[cid] = run.get(cid, 0) + 1 if shut(st) else 0
            if run[cid] > max_shut_s * FPS:
                out.append(("UZUN_KAPALI", cid, round(t, 2)))
    return out


@pytest.mark.parametrize("name", sorted(te.CONFIGS))
def test_eyes_open_and_on_target_during_throw(tmp_path, monkeypatch, name):
    plan, des = laughing_throw(tmp_path, name)
    bad = problems(face_states(plan, des, monkeypatch), bin_x=te.CONFIGS[name][4])
    assert not bad, bad[:6]


def test_laugh_still_closes_the_eyes_in_bursts(tmp_path, monkeypatch):
    """Gülme ifadesi kaybolmaz: eylem dışında gözler bir süre kapanır."""
    plan, des = laughing_throw(tmp_path, "yetiskin_saga")
    rows = face_states(plan, des, monkeypatch, 3.8, 6.0)
    for cid in rows[0][1]:
        n = sum(shut(c[cid][0]) for _t, c in rows)
        assert 0 < n < len(rows), (cid, n, len(rows))


def test_open_and_shut_laughing_eyes_differ_on_screen():
    des = pp.derive_design({"id": "s_k", "age": 3, "role": "kız"}, {"height_m": 0.98})
    base = {"mouth": "X", "blink": 0, "emotion": LAUGH, "gaze": 0.0, "brow": 0.0, "pulse": 0.0}
    for view in (fv.VIEWS[0], fv.VIEWS[5]):
        a = fv.render(des, fv.pose(*view), base)
        b = fv.render(des, fv.pose(*view), dict(base, eyes_open=True))
        assert fv._changed(a, b).histogram()[255] > 200, view[0]


# ---------------------------------------------------------------- bilerek eklenen hata
def test_eyes_shut_through_the_whole_laugh_is_caught(tmp_path, monkeypatch):
    """Eski davranış: gülme ifadesi gözü sürekli kapatır, bakış eylemi izlemez."""
    monkeypatch.setattr(r2, "eyes_state", lambda emo, lt, seed, blink, watching: (blink, False))
    monkeypatch.setattr(r2, "action_look", lambda beat, lt: None)
    plan, des = laughing_throw(tmp_path, "yetiskin_saga")
    kinds = {b[0] for b in problems(face_states(plan, des, monkeypatch))}
    assert {"EYLEMDE_GOZ_KAPALI", "UZUN_KAPALI"} <= kinds, kinds
