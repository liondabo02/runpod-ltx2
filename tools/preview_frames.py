#!/usr/bin/env python3
"""Hızlı görsel kontrol: bir bölümden seçilen saniyelerin karelerini çizip tek bir önizleme sayfası (PNG) yapar. Tam render beklemeden motoru görmek için.
python tools\\preview_frames.py --series-id ahos-bizim-aile --episode e001 --times 3,40,100,200 --out studio\\reports\\onizleme.png"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import shot_planner as sp  # noqa: E402
import puppet2d as pp2  # noqa: E402
import render2d as r2  # noqa: E402
from PIL import Image  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series-id", required=True); ap.add_argument("--episode", required=True)
    ap.add_argument("--times", required=True); ap.add_argument("--out", required=True); ap.add_argument("--cols", type=int, default=2)
    a = ap.parse_args()
    sdir = os.path.join(ROOT, "series", a.series_id); ep = os.path.join(sdir, "episodes", a.episode)
    bible = json.load(open(os.path.join(sdir, "series-bible.json"), encoding="utf-8")); assets = os.path.join(sdir, "assets")
    designs = {}
    for ch in bible["characters"]:
        p = os.path.join(assets, ch["id"] + ".spec.json")
        designs[ch["id"]] = pp2.derive_design(ch, json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {})
    ims = []
    for t in [float(x) for x in a.times.split(",")]:
        plan = sp.plan(ep, bible, assets, max(0.0, t - 0.2), t + 0.2)
        im = r2.frame(plan, designs, t)
        if im is not None:
            ims.append(im.resize((640, 360)))
    cols = max(1, a.cols); rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (640 * cols, 360 * rows), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); sheet.save(a.out)
    print("ÖNİZLEME:", a.out, len(ims), "kare")


if __name__ == "__main__":
    main()
