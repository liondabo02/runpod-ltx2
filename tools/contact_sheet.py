"""Temas kare dizisi: verilen aralıkta kare kare (fps adımıyla) gerçek motor çıktısını bir sayfaya dizer. İç QA (kullanıcıya gönderilmez).
Kullanım: contact_sheet.py <bölüm_dizini> <seri_bible.json> <t0> <t1> <çıktı.png> [adım_sn=0.1] [sütun=6]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import puppet2d as pp, render2d as r2, shot_planner as sp
from PIL import Image

def build(ep, bible_path, t0, t1):
    bible = json.load(open(bible_path, encoding="utf-8")); series_dir = os.path.dirname(os.path.abspath(bible_path)); assets = os.path.join(series_dir, "assets")
    plan = sp.plan(ep, bible, assets, t0, t1)
    designs = {}
    for ch in bible["characters"]:
        spp = os.path.join(assets, f"{ch['id']}.spec.json")
        designs[ch["id"]] = pp.derive_design(ch, json.load(open(spp, encoding="utf-8")) if os.path.exists(spp) else {})
    return plan, designs

def sheet(ep, bible_path, t0, t1, out, step=0.1, cols=6, w=426):
    plan, designs = build(ep, bible_path, t0, t1)
    ts = []; t = t0
    while t <= t1 + 1e-9:
        ts.append(round(t, 3)); t += step
    h = int(w * 9 / 16); rows = (len(ts) + cols - 1) // cols
    S = Image.new("RGB", (w * cols, h * rows), (255, 255, 255))
    for i, t in enumerate(ts):
        im = r2.frame(plan, designs, t).resize((w, h))
        S.paste(im, ((i % cols) * w, (i // cols) * h))
    S.save(out); return ts

if __name__ == "__main__":
    a = sys.argv
    print(sheet(a[1], a[2], float(a[3]), float(a[4]), a[5], float(a[6]) if len(a) > 6 else 0.1, int(a[7]) if len(a) > 7 else 6))
