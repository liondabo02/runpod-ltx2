import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import object_state as O, render2d as r2, shot_motion as sm, setpieces2d, turn_sheet as T
BIBLE = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile", "series-bible.json")
DES = T.design_set(BIBLE)
TG = setpieces2d.TARGETS

PICK = [{"t": 0, "at": [-1.3, 0.0]}, {"t": 1.6, "at": [-1.3, 0.0]}, {"t": 2.8, "holder": "aden"}, {"t": 5, "holder": "aden"}]
GIVE = [{"t": 0, "holder": "aden"}, {"t": 2.0, "holder": "aden"}, {"t": 3.4, "holder": "harun"}, {"t": 9, "holder": "harun"}]
TOSS = [{"t": 0, "holder": "harun"}, {"t": 2.0, "holder": "harun"}, {"t": 3.2, "at": "bin_green", "hide": True}]
DROP = [{"t": 0, "holder": "aden"}, {"t": 1.0, "holder": "aden"}, {"t": 1.8, "at": [0.2, 0.0]}, {"t": 3, "at": [0.2, 0.0]}]

def test_states_pickup_hold_handoff_drop_dispose():
    assert O.state_at(PICK, 0.5)["state"] == "ground" and O.state_at(PICK, 2.0)["state"] == "pickup" and O.state_at(PICK, 4.0)["state"] == "held"
    assert O.state_at(GIVE, 2.7)["state"] == "transfer" and O.state_at(GIVE, 2.7)["to"] == "harun" and O.state_at(GIVE, 5)["holder"] == "harun"
    assert O.state_at(DROP, 1.4)["state"] == "put" and O.state_at(DROP, 2.5)["state"] == "ground"
    assert O.state_at(TOSS, 2.5)["state"] == "put" and O.state_at(TOSS, 3.3)["state"] == "hidden"

def test_events_and_reach_windows_for_sfx_and_motion():
    assert [e["type"] for e in O.events(PICK)] == ["pickup"] and O.events(PICK)[0]["t"] == 2.8
    assert [e["type"] for e in O.events(GIVE)] == ["handoff"]
    assert [e["type"] for e in O.events(DROP)] == ["drop"] and [e["type"] for e in O.events(TOSS)] == ["dispose"]
    w = {x["actor"]: x for x in O.reach_windows(GIVE)}
    assert w["aden"]["kind"] == "give" and w["harun"]["kind"] == "take" and w["harun"]["t0"] < w["harun"]["t1"] == 3.4     # alıcı kolu önceden uzatır

def test_validation_catches_bad_tracks():
    cast = ["aden", "harun"]
    assert O.validate(PICK, cast, TG) == [] and O.validate(GIVE, cast, TG) == [] and O.validate(TOSS, cast, TG) == [] and O.validate(DROP, cast, TG) == []
    assert any("sırasız" in p for p in O.validate([{"t": 2, "at": [0, 0]}, {"t": 1, "at": [0, 0]}], cast, TG))
    assert any("bilinmeyen sahip" in p for p in O.validate([{"t": 0, "holder": "ghost"}], cast, TG))
    assert any("bilinmeyen hedef" in p for p in O.validate([{"t": 0, "at": "bin_pink"}], cast, TG))
    assert any("ışınlanma" in p for p in O.validate([{"t": 0, "at": [0, 0]}, {"t": 1, "at": [2, 0]}], cast, TG))       # elde olmadan yerden yere gidemez
    assert any("çok kısa" in p for p in O.validate([{"t": 0, "holder": "aden"}, {"t": 0.05, "holder": "harun"}], cast, TG))
    assert any("hide sonrası" in p for p in O.validate(TOSS + [{"t": 4, "at": "bin_green"}], cast, TG))
    assert any("tam olarak biri" in p for p in O.validate([{"t": 0, "holder": "aden", "at": [0, 0]}], cast, TG))

def test_e900_beat_tracks_are_valid():
    bs = json.load(open(os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile", "episodes", "e900_kabul", "beat_sheet.json"), encoding="utf-8"))
    n = 0
    for b in bs["beats"]:
        for ob in (b.get("choreo") or {}).get("objects", []):
            assert O.validate(ob["track"], b.get("characters") or ["aden", "harun"], TG) == [], (b.get("id"), ob)
            n += 1
    assert n >= 4

def test_weight_changes_carry_pose():
    light, heavy = O.carry_adjust(O.weight_of("balloon")), O.carry_adjust(O.weight_of("stone"))
    assert heavy["lean"] < light["lean"] and heavy["speed"] < light["speed"] and heavy["sq"] < light["sq"]

def _scene(track, a_kind, h_kind, fps=24):
    """İki gerçek karakter, gerçek pozlar, gerçek el konumları: nesne konumu kare kare."""
    da, dh = DES["aden"], DES["harun"]
    def items_at(t):
        pa = sm.pose_at(a_kind, t, 9.0, 0, 0.2, 0.2, da["height"], 0.5 * da["height"])
        ph = sm.pose_at(h_kind, t, 9.0, 1, 1.4, 1.4, dh["height"], 0.5 * dh["height"])
        return [("aden", da, pa, {"kind": a_kind, "x0": 0.2, "x1": 0.2}, 0, 0), ("harun", dh, ph, {"kind": h_kind, "x0": 1.4, "x1": 1.4}, 0, 0)]
    def hold(holder, t, hand=None):
        h = r2._hold_pos(holder, items_at(t), DES, {}, t, hand); return h[0], h[1]
    return hold, (lambda at: tuple(TG[at]) if isinstance(at, str) else tuple(at))

def test_handoff_object_does_not_jump_between_hands():
    hold, tgt = _scene(GIVE, "reach", "idle")
    worst, at = O.max_jump(GIVE, hold, tgt, fps=24)
    assert worst < 0.12, (worst, at)                 # 24 fps'de kare başına 12 cm'den büyük sıçrama yok (elden ele ~1 m'yi 1.4 sn'de gider)

def test_object_is_in_hand_when_held_and_matches_hand_anchor():
    from puppet2d import hand_offset
    hold, tgt = _scene(PICK, "reach", "idle")
    x, y, st = O.position(PICK, 4.0, hold, tgt)
    assert st["state"] == "held"
    da = DES["aden"]; pa = sm.pose_at("reach", 4.0, 9.0, 0, 0.2, 0.2, da["height"], 0.5 * da["height"])
    cand = [0.2 + hand_offset(da, pa, s)[0] for s in "LR"]
    assert min(abs(x - c) for c in cand) < 1e-6                           # nesne iki elden birinin çizilen konumunda

def test_deterministic_and_hidden_returns_none():
    hold, tgt = _scene(TOSS, "idle", "reach")
    a = [O.position(TOSS, t / 10, hold, tgt)[:2] for t in range(0, 40)]
    b = [O.position(TOSS, t / 10, hold, tgt)[:2] for t in range(0, 40)]
    assert a == b and a[-1] == (None, None)


def test_render_links_reach_window_and_weight():
    beat = {"choreo": {"objects": [{"prop": "stone", "track": GIVE}]}}
    # alıcı (harun) temas 3.4 sn'den ÖNCE uzanmaya başlar; verici (aden) 2.0'dan itibaren
    rh, wh = r2.object_effects(beat, "harun", 2.9); assert rh is not None and rh[0] > 0
    assert r2.object_effects(beat, "harun", 0.5)[0] is None
    ra, wa = r2.object_effects(beat, "aden", 1.0); assert ra is None and wa > 1.0          # elinde taş taşıyor: ağırlık var
    assert r2.object_effects(beat, "aden", 8.0)[1] == 0.0                                  # artık taşımıyor
    assert r2.object_effects(beat, "harun", 8.0)[1] > 1.0
