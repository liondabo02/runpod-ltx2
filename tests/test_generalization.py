"""GENELLEME KANITI: motor, e900/ahos-bizim-aile'ye özgü HİÇBİR veri bilmeden, tamamen farklı bir sentetik projede (karakter adları/boyları, mekân kimlikleri,
dekor yerleşimi, nesneler, süreler) aynı türden sorunları çözüyor mu? Proje verisi test içinde üretilir; motor kodu değiştirilmez.
Ayrıca: motor kaynağında proje/bölüm adı yok (statik denetim)."""
import json, os, re, sys, random
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import shot_motion as sm, shot_planner as sp, render2d as r2, puppet2d as pp, staging, setpieces2d, object_state, render_worker as rw

TOOLS = os.path.join(os.path.dirname(__file__), "..", "tools")
ENGINE_FILES = ["continuity.py", "scene_contract.py", "staging.py", "render2d.py", "shot_planner.py", "setpieces2d.py", "object_state.py", "render_worker.py", "puppet2d.py", "shot_motion.py", "sfx_events.py", "action_staging.py", "readability.py"]
FORBIDDEN = ["e900", "harun", "aden", "park_trash_walk", "ahos-bizim", "SC01", "kabul"]


def test_engine_sources_contain_no_project_or_episode_names():
    for fn in ENGINE_FILES:
        txt = open(os.path.join(TOOLS, fn), encoding="utf-8").read().lower()
        for w in FORBIDDEN:
            assert w.lower() not in txt, f"{fn}: motor kodunda proje/bölüm verisi geçiyor: {w}"


def _mk_project(root, chars, locations, beats):
    os.makedirs(os.path.join(root, "assets"), exist_ok=True); ep = os.path.join(root, "episodes", "e1"); os.makedirs(ep, exist_ok=True)
    bible = {"series_id": "proje-b", "characters": [{"id": c, "name": c.title(), "age": 30, "role": "x"} for c in chars], "locations": [{"id": l, "name": l} for l in locations]}
    for c, h in chars.items():
        json.dump({"species": "human", "height_m": h, "hair_style": "bob", "palette": {"hair": [0.2, 0.1, 0.1], "skin": [0.9, 0.7, 0.6], "shirt": [0.2, 0.5, 0.4], "shorts": [0.1, 0.2, 0.3], "accent": [1, 0.8, 0.2]}}, open(os.path.join(root, "assets", f"{c}.spec.json"), "w"))
    json.dump({"schema": "x", "beats": beats}, open(os.path.join(ep, "beat_sheet.json"), "w"))
    return bible, ep


def _beat(t0, loc, cast, objs, motion, cam="orta"):
    return {"t_start": t0, "t_end": t0 + 9, "scene_id": "S", "location": loc, "characters": cast, "action": "", "dialogue": "", "camera": cam,
            "choreo": {"motion": motion, "objects": objs, "gaze": {}, "react": {}, "icons": []}}


def _designs(bible, root):
    out = {}
    for ch in bible["characters"]:
        out[ch["id"]] = pp.derive_design(ch, json.load(open(os.path.join(root, "assets", f"{ch['id']}.spec.json"))))
    return out


CASES = [  # (boylar, mekân dekoru x, nesne, başlangıç konumları)
    ({"mira": 1.55, "oz": 2.3}, -2.0, "stone", {"mira": -0.4, "oz": 1.1}),
    ({"bo": 0.7, "lena": 1.75}, 0.6, "flower", {"bo": 1.9, "lena": -1.5}),
    ({"tek": 1.2, "dev": 2.0}, 2.5, "bottle", {"tek": 0.0, "dev": 0.2}),
]


@pytest.mark.parametrize("heights,bin_x,prop,xs", CASES)
def test_other_projects_handoff_and_throw_are_physically_valid(tmp_path, heights, bin_x, prop, xs):
    a, b = list(heights)
    root = str(tmp_path / "proje_b")
    track = [{"t": 0, "holder": a}, {"t": 2.0, "holder": a}, {"t": 3.4, "holder": b}, {"t": 5.0, "holder": b}, {"t": 6.4, "at": "bin_yellow", "hide": True}]   # ver + at (aynı plan: çelişki olabilir, raporlanmalı)
    track2 = [{"t": 0, "holder": b}, {"t": 2.0, "holder": b}, {"t": 3.2, "at": "bin_blue", "hide": True}]
    bt = [_beat(0, "garaj_x", [a, b], [{"prop": prop, "track": [{"t": 0, "holder": a}, {"t": 2.0, "holder": a}, {"t": 3.4, "holder": b}, {"t": 6, "holder": b}]}],
                {a: {"kind": "idle", "x0": xs[a], "x1": xs[a]}, b: {"kind": "idle", "x0": xs[b], "x1": xs[b]}}),
          _beat(9, "garaj_x", [a, b], [{"prop": prop, "track": track2}], {a: {"kind": "idle", "x0": xs[a], "x1": xs[a]}, b: {"kind": "idle", "x0": xs[b], "x1": xs[b]}})]
    bible, ep = _mk_project(root, heights, ["garaj_x"], bt)
    json.dump({"garaj_x": {"pieces": [["bins", bin_x]]}}, open(os.path.join(root, "locations.json"), "w"))          # proje verisi: dekor yerleşimi
    plan = sp.plan(ep, bible, os.path.join(root, "assets"), 0, 18, fps=12)
    des = _designs(bible, root)
    # 1) hedefler proje verisinden gelir (başka x), motor sabiti değil
    p0, p1 = plan["beats"]
    assert abs(p0["targets"]["bin_green"][0] - bin_x) < 1e-6 and "bin_yellow" in p0["targets"]
    # 2) el değiştirme: fiziksel aralık (kol erişimi) sağlanır
    confl = [n for pb in plan["beats"] for n in pb["staging_notes"] if n["kind"] == "conflict"]
    dur0 = p0["t_end"] - p0["t_start"]
    xa, xb = (sm.motion_x(p0["motion"][c], 3.4, dur0, heights[c]) for c in (a, b))
    ratio = pp.handoff_reach_ratio(des[a], xa, des[b], xb)          # çizimin kullandığı AYNI erişim ölçüsü (omuz yüksekliği farkı dahil)
    assert ratio <= 1.0 or any(n["rule"] == "handoff_separation" for n in confl), (ratio, xa, xb)          # ya fiziksel olarak geçerli ya da çelişki AÇIKÇA bildirilmiş
    # 3) atış: okunur aralık (boya/ağırlığa göre), hedefe göre
    lo, hi = staging.throw_range(heights[b], object_state.weight_of(prop))
    dx = abs(p1["targets"]["bin_blue"][0] - p1["motion"][b]["x1"])
    assert (lo - 1e-6 <= dx <= hi + 1e-6) or any(n["rule"] == "throw_distance" and n["kind"] == "conflict" for n in confl), (dx, lo, hi)
    # 4) ışınlanma yok: yeniden konumlanan karakter yürüyerek gelir ve temastan önce varır
    for pb in plan["beats"]:
        for n in pb["staging_notes"]:
            if n["kind"] == "adjusted" and n["rule"] == "blocking":      # seyirci: eylemi korunur; yeni yere yaklaşma yürüyüşüyle, plan içinde varır
                m = pb["motion"][n["actor"]]; ap = m.get("approach")
                assert not ap or (ap["walk_s"] <= pb["t_end"] - pb["t_start"] and abs(m["x0"] - n["to"]) < 1e-3), m
            elif n["kind"] == "adjusted":
                m = pb["motion"][n["actor"]]; assert m["kind"] == "walk" and m.get("walk_s")
    # 5) karelerde (dünya ölçeğinde, çözünürlükten bağımsız) tutulan nesne elin yanında; render hatasız
    items_checked = 0
    for t in (4.0, 6.0, 11.0):
        im = r2.frame(plan, des, t); assert im.size == (1280, 720)
    # 6) devir ve atış sonrası nesne: tutan elin dünya konumuna ≤ 5 cm (tutuş payı) bağlı
    beat = p0; lt = 5.0
    items = []
    for cid in beat["cast"]:
        m = beat["motion"][cid]
        pose = sm.pose_at(m["kind"], lt, 9.0, m["seed"], m["x0"], m["x1"], des[cid]["height"], des[cid]["height"] * 0.45); items.append((cid, des[cid], pose, m, 0, 0))
    objs = r2._objects_now(beat, items, lt)
    assert len(objs) == 1 and objs[0][4] == b
    hx, hy = pp.hand_offset(des[b], items[1][2], objs[0][5]); grip = object_state.grip_of(prop, 0.55)
    assert abs(objs[0][1] - (items[1][2]["x"] + hx)) < 0.05 and abs(objs[0][2] - max(0.0, hy * 1 - grip)) < 0.06


def test_unsupported_location_and_target_are_reported_not_faked(tmp_path):
    root = str(tmp_path / "proje_c")
    a = "ela"
    bt = [_beat(0, "yeni_mekan", [a], [{"prop": "ball", "track": [{"t": 0, "holder": a}, {"t": 2, "holder": a}, {"t": 3, "at": "bin_green", "hide": True}]}], {a: {"kind": "idle", "x0": 0.0, "x1": 0.0}})]
    bible, ep = _mk_project(root, {a: 1.6}, ["yeni_mekan"], bt)
    plan = sp.plan(ep, bible, os.path.join(root, "assets"), 0, 9, fps=12)
    pb = plan["beats"][0]
    assert pb["targets"] == {} and any("locations.json" in g for g in pb["capability_gaps"])           # desteklenmeyen mekân: açık rapor
    # ön kontrol: bilinmeyen hedef -> BLOCKED (sessizce çizilmez, uydurulmaz)
    m = rw.run(ep, bible, 0, 9, root, "2d")
    assert m["status"] == "BLOCKED" and m["error"] == "NESNE_IZI_GECERSIZ" and any("bilinmeyen hedef" in p for p in m["problems"])
    json.dump({"yeni_mekan": {"pieces": [["fountain", 1.0]]}}, open(os.path.join(root, "locations.json"), "w"))   # katalogda olmayan parça
    pb2 = sp.plan(ep, bible, os.path.join(root, "assets"), 0, 9, fps=12)["beats"][0]
    assert any("fountain" in g for g in pb2["capability_gaps"])                                          # eksik yetenek raporlanır


def test_randomized_heights_positions_keep_physical_invariants():
    rnd = random.Random(7)
    for _ in range(200):
        ha, hb = rnd.uniform(0.5, 2.4), rnd.uniform(0.5, 2.4)
        xa, xb = rnd.uniform(-2, 2), rnd.uniform(-2, 2)
        mot = {"a": {"kind": "idle", "x0": xa, "x1": xa}, "b": {"kind": "idle", "x0": xb, "x1": xb}}
        ob = [{"prop": "x", "track": [{"t": 0, "holder": "a"}, {"t": 3.0, "holder": "a"}, {"t": 4.4, "holder": "b"}, {"t": 7, "holder": "b"}]}]
        notes = staging.resolve(mot, ob, {"a": ha, "b": hb}, {}, prev_x={"a": xa, "b": xb})
        reach = 0.27 * (ha + hb); sep = abs(mot["a"]["x1"] - mot["b"]["x1"])
        conflicts = [n for n in notes if n["kind"] == "conflict"]
        assert conflicts or (0.4 * reach - 1e-6 <= sep <= 0.95 * reach + 1e-6)
        for c in "ab":                                                           # ışınlanma yok: başlangıç = önceki konum
            assert abs(mot[c]["x0"] - (xa if c == "a" else xb)) < 1e-3
