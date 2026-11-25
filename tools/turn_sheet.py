"""Dönüş kontrol sayfası: her karakter ön / üç-çeyrek / yan (sağa-sola). İç QA içindir (kullanıcıya klip gönderilmez)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import puppet2d as pp, shot_motion as sm
from PIL import Image

def design_set(bible_path):
    ch = json.load(open(bible_path, encoding="utf-8"))["characters"]
    return {c["id"]: pp.derive_design(c, {}) for c in ch}

def render_view(des, yaw, ppm=200, size=(320, 400), blink=0, mouth="C", emotion="neutral"):
    cv = pp.Cv(size[0], size[1])
    p = sm.base_pose(0.0); p["yaw"] = yaw
    pp.draw_character(cv, des, p, {"mouth": mouth, "blink": blink, "emotion": emotion}, size[0] / 2, size[1] - 20, ppm, 0.3)
    im = cv.img.resize(size, Image.LANCZOS) if cv.img.size != size else cv.img
    return im

def sheet(designs, ids, out, ppm=200):
    views = [("front", 0.0), ("3/4", 0.6), ("side", 1.0), ("side-L", -1.0)]
    w, h = 320, 400
    S = Image.new("RGB", (w * len(views), h * len(ids)), (255, 255, 255))
    for r, i in enumerate(ids):
        for c, (_, yaw) in enumerate(views):
            S.paste(render_view(designs[i], yaw, ppm, (w, h)), (c * w, r * h))
    S.save(out); return out

if __name__ == "__main__":
    d = design_set(sys.argv[1]); sheet(d, sys.argv[3].split(","), sys.argv[2])
