"""Saç (kâkül dahil) gözleri örtmemeli: her saç tipi x yaş sınıfı x cinsiyet x ifade için, saçlı ve saçsız çizimin göz bölgesindeki farkı ölçülür. Sentetik karakterler; proje dosyası okunmaz."""
import os, sys, itertools

import pytest
from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import scenes2d as sc  # noqa: E402

BG = (200, 230, 200)
STYLES = ["bob", "bangs", "wavy_long", "short", "curly", "ponytail", "bun", "spiky"]
EMOS = ["neutral", "laugh", "happy", "surprise", "sad"]


def design(style, age, female):
    ch = {"id": f"f{style}{age}{female}", "name": "kız" if female else "oğlan", "age": age}
    return pp.derive_design(ch, {"height_m": {5: 0.95, 8: 1.2, 35: 1.75}[age], "hair_style": style} if style else {"height_m": 1.2})


def draw(d, emo, style=None, view="front"):
    d = dict(d, hair_style=style if style is not None else d["hair_style"])
    cam = sc.Cam(0.0, d["height"] * 0.8, 3.0)
    pose = {"x": 0.0, "z": 0.0, "yaw": 0.0, "lean": 0.0, "sq": 1.0, "view": view, "head": [0.0, 0.0, 0.0], "aL": [0.0, 0.1], "aR": [0.0, -0.1], "lL": 0.0, "lR": 0.0}
    st = {"mouth": "X", "blink": 0, "emotion": emo, "gaze": 0.0, "brow": 0.0, "pulse": 0.0}
    cv = pp.Cv(ss=1); cv.img.paste(BG, (0, 0, pp.W, pp.H))
    pp.draw_character(cv, d, pose, st, cam.x(0.0), cam.y(0.0), cam.s, 0.0)
    return cv.img, cam


def covered_eye_fraction(d, emo):
    """Göz özelliği (beyaz/ink/iris) pikselleri içinden saçın üstüne çizdiği oran."""
    with_hair, cam = draw(d, emo)
    bare, _ = draw(d, emo, style="none")
    skin = tuple(d["skin"])
    # yüz kutusu: saçsız çizimde ten rengindeki piksellerin sınırı
    sk = Image.eval(ImageChops.difference(bare, Image.new("RGB", bare.size, skin)).convert("L"), lambda v: 255 if v < 12 else 0)
    bx = sk.getbbox()
    assert bx, "yüz bulunamadı"
    x0, y0, x1, y1 = bx
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    box = (int(cx - 0.34 * w), int(cy - 0.22 * h), int(cx + 0.34 * w), int(cy + 0.12 * h))
    feat = ImageChops.difference(bare.crop(box), Image.new("RGB", (box[2] - box[0], box[3] - box[1]), skin)).convert("L").point(lambda v: 255 if v > 40 else 0)
    n = feat.histogram()[255]
    if n < 30:
        return 0.0, n
    over = ImageChops.difference(with_hair.crop(box), bare.crop(box)).convert("L").point(lambda v: 255 if v > 30 else 0)
    hit = ImageChops.darker(feat, over).histogram()[255]
    return hit / n, n


CASES = list(itertools.product(STYLES, [5, 8, 35], [True, False], EMOS))


@pytest.mark.parametrize("style,age,female,emo", CASES)
def test_hair_never_covers_the_eyes(style, age, female, emo):
    frac, n = covered_eye_fraction(design(style, age, female), emo)
    assert frac <= 0.05, (style, age, female, emo, round(frac, 3), n)
