"""Gözler ve kaşlar her saç tipinde / başlıkta okunur. Ölçü çizilen piksellerden (tools/face_visibility.py). Yalnız sentetik tasarımlar."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import face_visibility as fv  # noqa: E402
import puppet2d as pp  # noqa: E402
import render2d as r2  # noqa: E402
import render_worker  # noqa: E402

KIDS = {"kucuk": (3, 0.98, "kız"), "yetiskin": (35, 1.9, "erkek")}
EMOS = ("happy", "laugh", "surprise", "sly")
VIEWS = tuple(v for v in fv.VIEWS if v[0] in ("front", "front_turn_l", "three_quarter_r", "side_r", "side_l"))
# (saç, aksesuar, tür)
LOOKS = [("bob", "none", "human"), ("bangs", "none", "human"), ("short", "none", "human"), ("spiky", "none", "human"), ("hijab", "none", "human"),
         ("wavy_long", "bow", "human"), ("curly", "star", "human"), ("bun", "glasses", "human"), ("ponytail", "hat", "human"),
         ("bob", "beanie", "human"), ("bald", "glasses", "human"), ("hijab", "flower_pin", "human"), ("spiky", "none", "hedgehog")]


def design(who, style, acc="none", species="human", **pal):
    age, h, role = KIDS[who]
    return pp.derive_design({"id": f"s_{who}", "age": age, "role": role},
                            {"height_m": h, "hair_style": style, "accessory": acc, "species": species, "palette": pal})


def bad_rows(des, emotions=EMOS, views=VIEWS, blinks=(0,)):
    out = []
    for e in emotions:
        for v in views:
            for b in blinks:
                why = fv.failures(fv.measure(des, e, v, blink=b))
                if why:
                    out.append((e, v[0], b, why))
    return out


@pytest.mark.parametrize("who", sorted(KIDS))
@pytest.mark.parametrize("style,acc,species", LOOKS)
def test_eyes_and_brows_stay_readable(who, style, acc, species):
    bad = bad_rows(design(who, style, acc, species))
    assert not bad, bad[:4]


@pytest.mark.parametrize("hair", [(0.12, 0.10, 0.12), (0.90, 0.75, 0.31), (0.92, 0.92, 0.94)], ids=["koyu", "sari", "ak"])
def test_brows_over_fringe_readable_for_dark_blond_and_white_hair(hair):
    bad = bad_rows(design("kucuk", "bob", hair=hair), emotions=("neutral", "happy", "angry", "sad", "surprise"))
    assert not bad, bad[:4]


def test_blink_and_closed_laughing_eyes_stay_readable():
    bad = bad_rows(design("kucuk", "bob"), emotions=("neutral", "laugh"), blinks=(1,))
    assert not bad, bad[:4]


SKINS = {"acik": (1.0, 0.87, 0.75), "esmer": (0.62, 0.44, 0.30), "koyu": (0.42, 0.28, 0.19), "cok_koyu": (0.27, 0.18, 0.13)}


@pytest.mark.parametrize("skin", sorted(SKINS))
@pytest.mark.parametrize("style,acc", [("bob", "none"), ("bald", "none"), ("hijab", "none")])
def test_brows_and_eyes_readable_on_every_skin_tone(skin, style, acc):
    for hair in ((0.12, 0.10, 0.12), (0.45, 0.28, 0.14), (0.90, 0.75, 0.31)):
        bad = bad_rows(design("kucuk", style, acc, skin=SKINS[skin], hair=hair), emotions=("neutral", "happy", "surprise"))
        assert not bad, (hair, bad[:4])


@pytest.mark.parametrize("spec", [{"eye_scale": 0.8}, {"eye_scale": 1.25, "eye_shape": "wide"}, {"face_w": 0.85, "eye_dist": 1.15}, {"brow_w": 1.5, "brow_shape": "arched"}],
                         ids=["kucuk_goz", "buyuk_goz", "dar_yuz", "kalin_kas"])
@pytest.mark.parametrize("style,acc", [("bob", "none"), ("short", "beanie"), ("spiky", "glasses")])
def test_spec_face_variants_stay_readable(spec, style, acc):
    des = pp.derive_design({"id": "s_v", "age": 35, "role": "kız"}, dict(spec, height_m=1.9, hair_style=style, accessory=acc))
    bad = bad_rows(des, emotions=("neutral", "laugh", "surprise"))
    assert not bad, bad[:4]


# ---------------------------------------------------------------- bilerek eklenen hatalar
def test_lowered_fringe_is_caught(monkeypatch):
    """Eski davranış: küt kâkül göz penceresine kırpılmaz."""
    monkeypatch.setattr(pp, "above", lambda pts, limit, cx, half: pts)
    why = fv.failures(fv.measure(design("kucuk", "bob"), "laugh"))
    assert any(w.startswith("eyes") for w in why), why


def test_fringe_lowered_by_a_little_is_caught(monkeypatch):
    real = pp.window_top
    monkeypatch.setattr(pp, "window_top", lambda eye_y, ery, ow: real(eye_y, ery, ow) + ery * 0.7)
    why = fv.failures(fv.measure(design("kucuk", "bob"), "surprise"))
    assert any(w.startswith("eyes") for w in why), why


def test_brow_in_hair_colour_over_fringe_is_caught(monkeypatch):
    monkeypatch.setattr(pp, "brow_colour", lambda base, under, skin, over=True: base)
    for v in (fv.VIEWS[0], fv.VIEWS[5]):
        why = fv.failures(fv.measure(design("kucuk", "bob"), "surprise", v))
        assert any(w.startswith("brows") for w in why), (v[0], why)


def test_brow_that_melts_into_dark_skin_is_caught(monkeypatch):
    """Eski davranış: kaş rengi yalnız saçtan türetilir."""
    monkeypatch.setattr(pp, "brow_colour", lambda base, under, skin, over=True: base)
    why = fv.failures(fv.measure(design("kucuk", "bald", skin=SKINS["koyu"], hair=(0.45, 0.28, 0.14)), "neutral"))
    assert any(w.startswith("brows") for w in why), why


def test_headwear_pulled_over_the_eyes_is_caught(monkeypatch):
    """Eski davranış: bere gözün üstüne iner."""
    real = pp.headwear_edge
    monkeypatch.setattr(pp, "headwear_edge", lambda eye_y, ery, bw, ow: real(eye_y, ery, bw, ow) + ery * 2.2)
    for v in (fv.VIEWS[0], fv.VIEWS[5]):
        why = fv.failures(fv.measure(design("kucuk", "short", "beanie"), "happy", v))
        assert any(w.startswith("eyes") for w in why), (v[0], why)


def test_frame_bar_drawn_across_the_eyes_is_caught(monkeypatch):
    """Eski davranış sınıfı: gözden kayan çerçeve gözün üstünden geçer; burada kalın bir koyu şerit gözün üstüne çizilir."""
    real = pp.draw_character

    def barred(cv, d, pose, st, fx, fy, ppm, t=0.0):
        real(cv, d, pose, st, fx, fy, ppm, t)
        if d.get("accessory") == "glasses":
            height = d["height"] * ppm
            for k in range(60):
                y = fy - height * (0.86 - 0.006 * k)
                if k % 3 == 0:
                    cv.line([(fx - height * 0.3, y), (fx + height * 0.3, y)], pp.INK, max(3.0, height * 0.008))
    monkeypatch.setattr(pp, "draw_character", barred)
    why = fv.failures(fv.measure(design("yetiskin", "bun", "glasses"), "neutral", fv.VIEWS[0]))
    assert any(w.startswith("eyes") for w in why), why


def test_measure_refuses_an_empty_mask():
    assert any("ölçülecek piksel yok" in w for w in fv.failures({"eyes": 1.0, "eyes_px": 0, "brows": 1.0, "brows_px": 500}))


# ---------------------------------------------------------------- üretim kapısı
def gate_project(tmp_path, spec):
    root = tmp_path / "p"; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": "p", "characters": [{"id": "ela", "name": "ela", "age": 4, "role": "kız"}, {"id": "gizli", "name": "gizli", "age": 40}]}
    json.dump(spec, open(root / "assets" / "ela.spec.json", "w"))
    json.dump({}, open(root / "locations.json", "w")); json.dump(bible, open(root / "series-bible.json", "w"))
    beat = {"t_start": 0, "t_end": 3, "scene_id": "S1", "shot_id": "p1", "location": "", "characters": ["ela"], "action": "", "camera": "orta",
            "choreo": {"motion": {"ela": {"kind": "idle", "x0": 0.0}}}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return root, ep, bible


def test_render_gate_stops_a_hidden_face_before_drawing_frames(tmp_path, monkeypatch):
    root, ep, bible = gate_project(tmp_path, {"height_m": 1.0, "hair_style": "bob"})
    monkeypatch.setattr(pp, "above", lambda pts, limit, cx, half: pts)
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: pytest.fail("yüzü kapalı karakter çizime girdi"))
    m = render_worker.run(str(ep), bible, 0, 3, str(root))
    assert m["status"] == "BLOCKED" and m["error"] == "YUZ_OKUNAMIYOR", m
    assert all("[character_drawing]" in p and " ela:" in p for p in m["problems"]), m["problems"]
    rep = json.load(open(ep / "render" / "face_visibility.json", encoding="utf-8"))
    assert list(rep["characters"]) == ["ela"]                       # yalnız planda oynayanlar ölçülür


def test_render_gate_lets_a_readable_face_through_to_drawing(tmp_path, monkeypatch):
    root, ep, bible = gate_project(tmp_path, {"height_m": 1.0, "hair_style": "bob"})
    reached = []
    monkeypatch.setattr(r2, "render_window", lambda plan_, des_, out_, **k: os.makedirs(out_, exist_ok=True) or reached.append(1) or {"missing": 1})
    m = render_worker.run(str(ep), bible, 0, 3, str(root))
    assert reached and m["error"] == "FRAMES_MISSING", m
