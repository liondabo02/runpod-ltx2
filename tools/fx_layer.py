# -*- coding: utf-8 -*-
"""AHOS efekt katmanı: gerçek 2D çizgi filmlerde olup bizde olmayan 'yaşam' katmanları (yalnız PIL; numpy varsa hızlanır).
- icons(): eylem metninden duygu simgeleri (kalp, uyku zzz, şaşkınlık '!', parıltı, müzik notası, ter damlası) karakterin başının üstünde, yumuşak zıplayarak.
- post(): ortam parçacıkları (polen/toz, yaprak/çiçek yaprağı), güneş ışığı huzmesi, sahne geçişi (iris açılış), kapanışta karartma.
Hepsi t'ye bağlı ve deterministiktir (aynı kare her seferinde aynı çıkar; çok işlemcili render ile uyumlu)."""
import math, re
from PIL import Image, ImageDraw, ImageFilter

ICON_RULES = [
    (r"sarıl|kucak|öp|seviş|sevgi|kalp", "heart"),
    (r"uyu|uykuda|mışıl|mırıltı|beşik", "zzz"),
    (r"şaşır|irkil|hay aksi|fark eder|aniden", "exclaim"),
    (r"ışılda|parla|yıldız|harika|bayram|alkış|kutla", "sparkle"),
    (r"şarkı|ıslık|dans|hoplar|neşe", "note"),
    (r"telaş|panik|yetişemez|kaçır", "sweat"),
]


def _h(*a):
    h = 2166136261
    for v in a:
        h = ((h ^ (int(v * 977) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 4294967295.0


def kinds_for(text):
    t = str(text).lower(); out = []
    for pat, k in ICON_RULES:
        if re.search(pat, t) and k not in out:
            out.append(k)
    return out[:2]


def _heart(d, x, y, r, col=(235, 70, 100)):
    d.ellipse([x - r, y - r, x, y + r * 0.2], fill=col); d.ellipse([x, y - r, x + r, y + r * 0.2], fill=col)
    d.polygon([(x - r * 0.98, y - r * 0.15), (x + r * 0.98, y - r * 0.15), (x, y + r * 1.15)], fill=col)


def _star(d, x, y, r, col=(255, 224, 70)):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5; rr = r if i % 2 == 0 else r * 0.42
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=col, outline=(70, 45, 20))


def icons(cv, cam, beat, xs, heights, t, lt):
    """Karakter başlarının üstünde duygu simgeleri. cv: pp.Cv (süper-örnekli tuval), cam: sc.Cam."""
    ks = beat.get("icons") or []
    if not ks or not xs:
        return
    s = cam.s; ss = cv.ss
    d = cv.d
    pop = min(1.0, lt / 0.25)                                   # pop-in
    bounce = 1.0 + 0.08 * math.sin(t * 7.0)
    for k_i, kind in enumerate(ks):
        for i, (x, hgt) in enumerate(zip(xs, heights)):
            if kind == "zzz" and hgt > 0.9:                      # uyku yalnız bebeklerde
                continue
            if kind in ("heart", "sparkle") and i > 1:
                continue
            wx = cam.x(x) * ss + (i * 0.1 + k_i * 0.35) * s * ss * 0.3
            wy = cam.y(hgt * 1.12 + 0.18 + 0.05 * math.sin(t * 3 + i)) * ss
            r = 0.085 * s * ss * pop * bounce
            if kind == "heart":
                for j in range(3):
                    ph = (t * 0.7 + j / 3.0 + _h(i, j)) % 1.0
                    _heart(d, wx + math.sin(ph * 6 + j) * r, wy - ph * 0.5 * s * ss, r * (0.7 + 0.4 * (1 - ph)) * (1 - ph * 0.5))
            elif kind == "zzz":
                for j in range(3):
                    ph = (t * 0.45 + j / 3.0) % 1.0
                    sz = 0.05 * s * ss * (0.6 + ph)
                    xx, yy = wx + ph * 0.25 * s * ss, wy - ph * 0.42 * s * ss
                    d.text((xx, yy), "Z", fill=(70, 90, 170), font=None)
                    d.line([(xx, yy), (xx + sz, yy), (xx, yy + sz), (xx + sz, yy + sz)], fill=(70, 90, 170), width=max(2, int(ss * 2)))
            elif kind == "exclaim" and lt < 1.4:
                a = min(1.0, lt / 0.12) * (1 - max(0.0, (lt - 0.9) / 0.5))
                bw = 0.055 * s * ss * a
                d.rounded_rectangle([wx - bw, wy - 0.28 * s * ss * a, wx + bw, wy - 0.07 * s * ss * a], radius=bw, fill=(240, 60, 50), outline=(70, 20, 20), width=max(2, ss * 2))
                d.ellipse([wx - bw * 0.9, wy - 0.045 * s * ss * a, wx + bw * 0.9, wy + 0.04 * s * ss * a], fill=(240, 60, 50), outline=(70, 20, 20), width=max(2, ss * 2))
            elif kind == "sparkle":
                for j in range(4):
                    ph = (t * 1.3 + j * 0.25 + _h(i, j, 7)) % 1.0
                    sx = wx + (_h(j, i, 3) - 0.5) * 0.7 * s * ss; sy = wy + (_h(j, i, 5) - 0.5) * 0.35 * s * ss
                    _star(d, sx, sy, 0.045 * s * ss * math.sin(ph * math.pi))
            elif kind == "note":
                for j in range(2):
                    ph = (t * 0.6 + j * 0.5) % 1.0
                    nx, ny = wx + (j - 0.5) * 0.3 * s * ss + math.sin(ph * 5) * 0.04 * s * ss, wy - ph * 0.4 * s * ss
                    rr = 0.03 * s * ss
                    d.ellipse([nx - rr, ny - rr * 0.7, nx + rr, ny + rr * 0.7], fill=(60, 60, 110))
                    d.line([(nx + rr, ny), (nx + rr, ny - rr * 3.4)], fill=(60, 60, 110), width=max(2, int(ss * 2)))
            elif kind == "sweat":
                ph = (t * 0.9 + i * 0.3) % 1.0
                sx, sy = wx + 0.12 * s * ss, wy + 0.1 * s * ss + ph * 0.18 * s * ss
                rr = 0.026 * s * ss
                d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr * 1.6], fill=(150, 205, 255), outline=(50, 90, 150))


def _particles(im, kind, t, seed, n=22):
    w, h = im.size
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(n):
        r0, r1, r2 = _h(i, seed, 1), _h(i, seed, 2), _h(i, seed, 3)
        sp = 0.015 + 0.03 * r2
        if kind == "pollen":                                     # içeride toz/polen: yavaş süzülür, parlar
            x = (r0 + t * sp * 0.6 + 0.04 * math.sin(t * 0.7 + i)) % 1.0 * w
            y = (r1 - t * sp * 0.5 + 0.03 * math.cos(t * 0.5 + i * 2)) % 1.0 * h
            a = int(70 + 70 * (0.5 + 0.5 * math.sin(t * 1.6 + i)))
            rr = 1.5 + 2.8 * r2
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 250, 220, a))
        else:                                                    # dışarıda yaprak/çiçek yaprağı: çapraz süzülür
            x = (r0 + t * sp * 1.6 + 0.02 * math.sin(t * 1.3 + i)) % 1.0 * w
            y = (r1 + t * sp * 1.1) % 1.0 * h
            ang = t * (1.5 + r2 * 2) + i
            ln = 3 + 3.5 * r2
            col = (255, 200, 215, 130) if i % 3 == 0 else (150, 200, 110, 110)
            dx, dy = math.cos(ang) * ln, math.sin(ang) * ln * 0.45
            d.ellipse([x - abs(dx), y - abs(dy) - 2, x + abs(dx), y + abs(dy) + 2], fill=col)
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def _rays(im, t, strength):
    w, h = im.size
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(4):
        x0 = w * (0.05 + 0.27 * i) + 18 * math.sin(t * 0.4 + i)
        wd = w * 0.08
        a = int(26 * strength * (0.7 + 0.3 * math.sin(t * 0.6 + i * 1.7)))
        d.polygon([(x0, 0), (x0 + wd, 0), (x0 + wd + w * 0.28, h), (x0 + w * 0.2, h)], fill=(255, 245, 200, a))
    ov = ov.filter(ImageFilter.GaussianBlur(14))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def _iris(im, p):
    """Sahne açılışı: daire büyüyerek görüntüyü açar (klasik çizgi film geçişi). p: 0..1"""
    w, h = im.size
    r = (math.hypot(w, h) / 2) * (0.04 + 0.96 * p ** 0.8)
    mask = Image.new("L", im.size, 0); ImageDraw.Draw(mask).ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], fill=255)
    bg = Image.new("RGB", im.size, (30, 24, 40))
    return Image.composite(im, bg, mask.filter(ImageFilter.GaussianBlur(2)))


def post(im, beat, t, lt, dur, total_s=480.0, first_of_scene=False):
    light = str(beat.get("light") or "").lower()
    outdoor = beat.get("scene") in ("garden", "path", "village", "park", "stage")
    seed = int(beat.get("i", 0)) // 6
    im = _particles(im, "leaf" if outdoor else "pollen", t, seed, n=0 if outdoor else 22)
    if re.search(r"güneş|sabah|öğle|parlak|altın", light):
        im = _rays(im, t, 1.0 if outdoor else 1.4)
    if first_of_scene and lt < 0.55:
        im = _iris(im, lt / 0.55)
    if t > total_s - 1.2:
        k = max(0.0, min(1.0, (total_s - t) / 1.2))
        im = Image.blend(Image.new("RGB", im.size, (20, 16, 26)), im, k)
    return im


def dust(cv, cam, x, direction, t, run=False, H=1.0):
    """Koşu/yürüyüşte ayak tozu ve (koşuda) hız çizgileri. Dünya koordinatı: x metre, zemin y=0. Karakterin ARKASINDA kalır."""
    n = 5 if run else 3
    for k in range(n):
        ph = ((t * (2.6 if run else 1.5)) + k / n) % 1.0
        bx = x - direction * (0.18 + 0.9 * ph * (1.4 if run else 0.8)) * H
        by = 0.03 * H + 0.16 * H * ph
        r = (0.035 + 0.07 * ph) * H
        a = 1.0 - ph
        col = (int(215 + 30 * (1 - a)), int(205 + 35 * (1 - a)), int(185 + 45 * (1 - a)))
        cv.ellipse(cam.x(bx), cam.y(by), r * cam.s, r * 0.8 * cam.s, col, None, 0)
    if run:
        for k in range(3):
            ly = (0.35 + 0.28 * k) * H
            ph = ((t * 3.1) + k * 0.37) % 1.0
            x0 = x - direction * (0.45 + 0.5 * ph) * H
            cv.line([(cam.x(x0), cam.y(ly)), (cam.x(x0 - direction * 0.55 * H), cam.y(ly))], (255, 255, 255), max(2.0, 0.02 * cam.s))
