# -*- coding: utf-8 -*-
"""AHOS arka plan 'boyama' katmanı: klasik TV çizgi filmindeki gibi arka plan karakterden ayrışır.
- yumuşatma (arka plan hafif odak dışı, karakter net => derinlik)
- atmosferik sis (uzak katman açık/mavimsi)
- ışık kaynağından sıcak/soğuk parıltı, sahneye göre ışık paleti (sabah, öğle, akşam, gece, iç mekân)
- boya/kağıt dokusu, köşe koyulaşması (ışık renginde)
Tümü yalnız numpy+PIL; cv.img (süper-örnekli tuval) üzerinde, karakterler çizilmeden ÖNCE çalışır. t'den bağımsız (kareler tutarlı)."""
import re
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

W, H = 1280, 720
_C = {}

# haze (uzak sis rengi), glow (ışık rengi), gpos (parıltı merkezi, ekran oranı), gk (güç), dark (köşe gölge rengi), dk (köşe gücü), sat
PAL = {
    "sabah":  dict(haze=(255, 236, 205), glow=(255, 226, 160), gpos=(0.82, 0.10), gk=0.34, dark=(70, 60, 110), dk=0.16, hk=0.20),
    "ogle":   dict(haze=(220, 240, 255), glow=(255, 250, 215), gpos=(0.70, 0.04), gk=0.24, dark=(40, 70, 90), dk=0.12, hk=0.16),
    "aksam":  dict(haze=(255, 190, 150), glow=(255, 160, 90), gpos=(0.15, 0.40), gk=0.46, dark=(80, 40, 90), dk=0.26, hk=0.26),
    "gece":   dict(haze=(70, 90, 150), glow=(150, 175, 255), gpos=(0.78, 0.12), gk=0.30, dark=(8, 12, 40), dk=0.45, hk=0.30),
    "bulut":  dict(haze=(200, 212, 230), glow=(235, 240, 250), gpos=(0.5, 0.0), gk=0.16, dark=(50, 60, 90), dk=0.18, hk=0.28),
    "ic":     dict(haze=(250, 235, 205), glow=(255, 232, 170), gpos=(0.78, 0.30), gk=0.30, dark=(70, 40, 40), dk=0.26, hk=0.0),
}


def _pick(light, kind):
    l = str(light or "").lower()
    if re.search(r"gece|ay ışığı|yıldız", l):
        return PAL["gece"]
    if re.search(r"gün batım|akşam|altın|kızıl", l):
        return PAL["aksam"]
    if re.search(r"bulut|kapalı|gölge|sis", l):
        return PAL["bulut"]
    if re.search(r"sabah|doğu", l):
        return PAL["sabah"]
    if kind in ("room", "stage"):
        return PAL["ic"]
    return PAL["ogle"]


def _grid():
    if "g" not in _C:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        _C["g"] = (xx / W, yy / H)
    return _C["g"]


def _grain():
    if "n" not in _C:
        rng = np.random.default_rng(11)
        n = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
        n = np.array(Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32) - 128.0
        _C["n"] = n / 40.0
    return _C["n"]


def _glow_mask(gpos, gk):
    key = ("m", gpos, gk)
    if key not in _C:
        xx, yy = _grid()
        d = np.sqrt(((xx - gpos[0]) * 1.1) ** 2 + ((yy - gpos[1]) * 1.6) ** 2)
        _C[key] = (np.clip(1.0 - d / 0.95, 0, 1) ** 1.8 * gk).astype(np.float32)
    return _C[key]


def _vig(dk):
    key = ("v", dk)
    if key not in _C:
        xx, yy = _grid()
        d = np.sqrt(((xx - 0.5) / 0.62) ** 2 + ((yy - 0.52) / 0.66) ** 2)
        _C[key] = (np.clip(d - 0.72, 0, 1) ** 1.3 * dk * 2.4).clip(0, 0.7).astype(np.float32)
    return _C[key]


def _haze_band(hk):
    key = ("h", hk)
    if key not in _C:
        _, yy = _grid()
        _C[key] = (np.clip(1.0 - np.abs(yy - 0.46) / 0.34, 0, 1) ** 1.2 * hk).astype(np.float32)
    return _C[key]


def enhance(cv, kind, light=None, t=0.0, blur=1.15):
    """cv.img'i yerinde günceller (süper-örnekli tuval). Karakterlerden önce çağrılmalı."""
    P = _pick(light, kind)
    ss = cv.ss
    small = cv.img.resize((W, H), Image.LANCZOS)
    if blur:
        small = small.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(small).astype(np.float32) / 255.0
    outdoor = kind not in ("room", "stage")
    if outdoor and P["hk"]:
        m = _haze_band(P["hk"])[..., None]
        a = a * (1 - m) + (np.array(P["haze"], np.float32) / 255.0) * m          # atmosferik perspektif (uzak: sisli)
    g = _glow_mask(P["gpos"], P["gk"])[..., None]
    gc = np.array(P["glow"], np.float32) / 255.0
    a = 1.0 - (1.0 - a) * (1.0 - g * gc)                                          # ekran (screen) karışımı: ışık parıltısı
    v = _vig(P["dk"])[..., None]
    dc = np.array(P["dark"], np.float32) / 255.0
    a = a * (1 - v) + (a * dc * 1.6) * v                                           # köşelerde renkli gölge (multiply)
    a = a + _grain()[..., None] * 0.012                                            # boya dokusu
    out = Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8))
    cv.img = out.resize((W * ss, H * ss), Image.BICUBIC) if ss != 1 else out
    cv.d = ImageDraw.Draw(cv.img)
