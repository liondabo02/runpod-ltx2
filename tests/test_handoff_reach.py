"""El değiştirme: konum çözücü çizimin kullandığı AYNI erişim ölçüsüyle (omuz yüksekliği farkı dahil) karar verir.
Rastgele boy çiftleri: sonuç ya fiziksel olarak geçerli (oran<=1) ya da çelişki AÇIKÇA bildirilir; hikâye (kim kime verir) değişmez."""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import puppet2d as pp, shot_motion as sm, staging


def _des(cid, h):
    return pp.derive_design({"id": cid, "name": cid, "age": 30, "role": "x"}, {"species": "human", "height_m": h, "palette": {}})


def test_random_height_pairs_resolve_by_drawing_reach_measure():
    rnd = random.Random(11); solved = conflicts = 0
    for _ in range(150):
        ha, hb = round(rnd.uniform(0.6, 2.4), 2), round(rnd.uniform(0.6, 2.4), 2)
        des = {"a": _des("a", ha), "b": _des("b", hb)}
        xa, xb = round(rnd.uniform(-1.8, 1.8), 2), round(rnd.uniform(-1.8, 1.8), 2)
        mot = {"a": {"kind": "idle", "x0": xa, "x1": xa, "seed": 1}, "b": {"kind": "idle", "x0": xb, "x1": xb, "seed": 2}}
        ob = [{"prop": "ball", "track": [{"t": 0, "holder": "a"}, {"t": 2.0, "holder": "a"}, {"t": 4.0, "holder": "b"}, {"t": 6.0, "holder": "b"}]}]
        fn = lambda by, x1, to, x2: pp.handoff_reach_ratio(des[by], x1, des[to], x2)
        notes = staging.resolve(mot, ob, {"a": ha, "b": hb}, {}, reach_fn=fn, dur=8.0)
        fx = {c: sm.motion_x(mot[c], 4.0, 8.0, h) for c, h in (("a", ha), ("b", hb))}
        ratio = pp.handoff_reach_ratio(des["a"], fx["a"], des["b"], fx["b"])
        said = any(n["kind"] == "conflict" and n["rule"] == "handoff_separation" for n in notes)
        assert ratio <= 1.0 or said, (ha, hb, xa, xb, ratio, notes)
        solved += ratio <= 1.0; conflicts += said
        assert [e["by"] for e in __import__("object_state").events(ob[0]["track"]) if e["type"] == "handoff"] == ["a"]      # niyet korunur
    assert solved >= 100 and solved + conflicts >= 150 - 5          # çoğu çözülür; çözülemeyen bildirilir
