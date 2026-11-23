# -*- coding: utf-8 -*-
"""Mekâna özel dekor parçaları (2D). Her mekân kimliği (bible location id) kendine ait ayırt edici nesnelerle çizilir; böylece
'park girişi', 'kaydırak alanı', 'çöp yolu' gibi yerler aynı çit+ağaç arka planı gibi görünmez. Zemin y=0, dünya metre cinsinden."""
import math
from puppet2d import INK, shade


def _o(cam):
    return max(2.0, 0.012 * cam.s)


def _rect(cv, cam, x0, y0, x1, y1, fill, ow=None):
    cv.poly([(cam.x(x0), cam.y(y0)), (cam.x(x1), cam.y(y0)), (cam.x(x1), cam.y(y1)), (cam.x(x0), cam.y(y1))], fill, INK, ow if ow is not None else _o(cam))


def _poly(cv, cam, pts, fill, ow=None):
    cv.poly([(cam.x(x), cam.y(y)) for x, y in pts], fill, INK, ow if ow is not None else _o(cam))


def _ell(cv, cam, x, y, rx, ry, fill, ow=None):
    cv.ellipse(cam.x(x), cam.y(y), rx * cam.s, ry * cam.s, fill, INK, ow if ow is not None else _o(cam))


def slide(cv, cam, x=1.5, t=0.0):
    _rect(cv, cam, x - 0.55, 0.0, x - 0.48, 1.35, (150, 150, 165))             # merdiven direği
    for k in range(5):
        _rect(cv, cam, x - 0.74, 0.22 + k * 0.24, x - 0.40, 0.27 + k * 0.24, (190, 190, 200))
    _rect(cv, cam, x - 0.62, 1.30, x - 0.10, 1.38, (230, 90, 70))              # platform
    _poly(cv, cam, [(x - 0.10, 1.38), (x - 0.10, 1.22), (x + 1.05, 0.10), (x + 1.15, 0.10), (x + 1.15, 0.18), (x + 0.02, 1.38)], (250, 200, 60))
    _rect(cv, cam, x - 0.35, 1.38, x - 0.30, 1.62, (150, 150, 165))
    _rect(cv, cam, x - 0.35, 1.58, x - 0.05, 1.63, (230, 90, 70))


def rules_sign(cv, cam, x=0.0, t=0.0):
    _rect(cv, cam, x - 0.05, 0.0, x + 0.05, 1.55, (130, 90, 55))
    _rect(cv, cam, x - 0.80, 1.55, x + 0.80, 2.45, (60, 140, 90))
    _rect(cv, cam, x - 0.74, 1.61, x + 0.74, 2.39, (245, 240, 220), _o(cam) * 0.6)
    for k, (c, sym) in enumerate([((60, 160, 90), "bin"), ((230, 190, 50), "flower"), ((230, 90, 70), "slide"), ((70, 130, 210), "walk")]):
        cx_, cy_ = x - 0.54 + k * 0.36, 2.0
        _ell(cv, cam, cx_, cy_, 0.15, 0.15, c, _o(cam) * 0.6)
        cv.line([(cam.x(cx_ - 0.07), cam.y(cy_)), (cam.x(cx_ + 0.07), cam.y(cy_))], (255, 255, 255), max(2.0, 0.02 * cam.s))
    cv.line([(cam.x(x - 0.6), cam.y(1.78)), (cam.x(x + 0.6), cam.y(1.78))], (80, 80, 80), max(2.0, 0.012 * cam.s))


def bins(cv, cam, x=1.2, t=0.0):
    for k, c in enumerate([(70, 160, 90), (240, 200, 60), (70, 120, 200)]):
        bx = x + k * 0.55
        _poly(cv, cam, [(bx - 0.2, 0.0), (bx + 0.2, 0.0), (bx + 0.24, 0.75), (bx - 0.24, 0.75)], c)
        _rect(cv, cam, bx - 0.27, 0.75, bx + 0.27, 0.83, shade(c, 0.8))
        _ell(cv, cam, bx, 0.42, 0.08, 0.08, (255, 255, 255), _o(cam) * 0.5)


def flower_bed(cv, cam, x=0.0, t=0.0):
    _rect(cv, cam, x - 1.4, 0.0, x + 1.4, 0.18, (120, 80, 50))
    cols = [(240, 90, 130), (250, 210, 60), (255, 255, 255), (170, 110, 220), (255, 140, 70)]
    for k in range(13):
        fx = x - 1.3 + k * 0.2167; sw = math.sin(t * 1.8 + k) * 0.015
        h = 0.34 + 0.12 * ((k * 7) % 4)
        cv.line([(cam.x(fx), cam.y(0.18)), (cam.x(fx + sw), cam.y(0.18 + h))], (60, 130, 60), max(2.0, 0.012 * cam.s))
        _ell(cv, cam, fx + sw, 0.18 + h, 0.075, 0.075, cols[k % 5], _o(cam) * 0.7)
        _ell(cv, cam, fx + sw, 0.18 + h, 0.025, 0.025, (250, 220, 80), 0)


def bike_lane(cv, cam, x=0.0, t=0.0):
    _rect(cv, cam, x - 3.5, -0.34, x + 3.5, -0.06, (205, 95, 80), 0)                  # bisiklet şeridi (kırmızı)
    _rect(cv, cam, x - 3.5, -0.62, x + 3.5, -0.34, (190, 185, 175), 0)                # yaya şeridi
    for k in range(-6, 7):
        _rect(cv, cam, x + k * 0.55, -0.355, x + k * 0.55 + 0.28, -0.325, (255, 255, 255), 0)
    bx = x + 1.8 + math.sin(t * 0.7) * 0.3
    for sg in (-1, 1):
        _ell(cv, cam, bx + sg * 0.32, 0.18, 0.18, 0.18, (230, 230, 235))
        _ell(cv, cam, bx + sg * 0.32, 0.18, 0.12, 0.12, (255, 255, 255), 0)
    cv.line([(cam.x(bx - 0.32), cam.y(0.18)), (cam.x(bx), cam.y(0.48)), (cam.x(bx + 0.32), cam.y(0.18))], (60, 60, 70), max(2.0, 0.016 * cam.s))
    cv.line([(cam.x(bx), cam.y(0.48)), (cam.x(bx + 0.22), cam.y(0.52))], (60, 60, 70), max(2.0, 0.016 * cam.s))


def gate(cv, cam, x=0.0, t=0.0):
    for sx in (-1.1, 1.1):
        _rect(cv, cam, x + sx - 0.12, 0.0, x + sx + 0.12, 2.1, (150, 105, 70))
    _rect(cv, cam, x - 1.3, 2.1, x + 1.3, 2.42, (200, 70, 60))
    _rect(cv, cam, x - 0.8, 2.15, x + 0.8, 2.37, (250, 240, 215), _o(cam) * 0.6)
    for k in range(6):
        _ell(cv, cam, x - 0.62 + k * 0.25, 2.26, 0.05, 0.05, (70, 150, 90), 0)


def picnic(cv, cam, x=0.0, t=0.0):
    _poly(cv, cam, [(x - 1.1, 0.0), (x + 1.1, 0.0), (x + 0.95, -0.34), (x - 0.95, -0.34)], (225, 95, 90))
    for k in range(5):
        _poly(cv, cam, [(x - 1.0 + k * 0.4, 0.0), (x - 0.84 + k * 0.4, 0.0), (x - 0.78 + k * 0.4, -0.34), (x - 0.92 + k * 0.4, -0.34)], (255, 245, 235), 0)
    _rect(cv, cam, x + 0.3, 0.0, x + 0.75, 0.3, (180, 130, 70))
    _poly(cv, cam, [(x + 0.3, 0.3), (x + 0.75, 0.3), (x + 0.65, 0.42), (x + 0.4, 0.42)], (200, 150, 85))


def kitchen(cv, cam, x=0.0, t=0.0):
    _rect(cv, cam, x - 3.0, 0.0, x - 0.9, 0.95, (235, 225, 205))
    _rect(cv, cam, x - 3.0, 0.95, x - 0.9, 1.03, (120, 90, 70))
    for k in range(3):
        _rect(cv, cam, x - 2.9 + k * 0.7, 1.7, x - 2.3 + k * 0.7, 2.4, (200, 150, 100))
    _rect(cv, cam, x + 1.1, 0.0, x + 2.4, 0.74, (175, 120, 70))                        # masa
    _rect(cv, cam, x + 1.0, 0.74, x + 2.5, 0.82, (205, 150, 90))
    _ell(cv, cam, x + 1.5, 0.92, 0.15, 0.1, (250, 250, 250)); _ell(cv, cam, x + 2.0, 0.92, 0.15, 0.1, (250, 250, 250))


def corridor(cv, cam, x=0.0, t=0.0):
    _rect(cv, cam, x - 0.5, 0.0, x + 0.55, 2.05, (135, 95, 60))                        # kapı
    _ell(cv, cam, x + 0.38, 1.0, 0.045, 0.045, (240, 200, 80), 0)
    _rect(cv, cam, x - 2.1, 0.0, x - 1.2, 0.35, (150, 110, 80))                        # ayakkabılık
    for k in range(3):
        _ell(cv, cam, x - 1.95 + k * 0.28, 0.42, 0.11, 0.06, (220, 100, 90), _o(cam) * 0.5)
    for k in range(3):
        _rect(cv, cam, x + 1.2 + k * 0.4, 1.55, x + 1.26 + k * 0.4, 1.62, (80, 80, 80), 0)
        _poly(cv, cam, [(x + 1.15 + k * 0.4, 1.55), (x + 1.35 + k * 0.4, 1.55), (x + 1.4 + k * 0.4, 0.95), (x + 1.1 + k * 0.4, 0.95)], [(90, 140, 200), (210, 110, 90), (110, 170, 110)][k])


def salon(cv, cam, x=0.0, t=0.0):
    _rect(cv, cam, x + 1.0, 0.0, x + 2.7, 0.55, (170, 90, 100))                        # kanepe
    _rect(cv, cam, x + 1.0, 0.55, x + 2.7, 1.1, (190, 105, 115))
    _rect(cv, cam, x + 0.9, 0.0, x + 1.1, 0.7, (150, 75, 85)); _rect(cv, cam, x + 2.6, 0.0, x + 2.8, 0.7, (150, 75, 85))
    _rect(cv, cam, x - 0.6, 0.0, x + 0.4, 0.38, (190, 140, 90))                        # sehpa


def wall_decor(cv, cam, x=0.0, t=0.0):
    """Referans: odalar poster, raf, abajur, perde gibi küçük detaylarla dolu (sade duvar yok)."""
    pos = [(-2.6, 1.55, 0.55, 0.75, (240, 200, 90)), (-1.7, 1.75, 0.45, 0.6, (120, 170, 220)),
           (2.9, 1.6, 0.6, 0.8, (230, 120, 110)), (3.7, 1.8, 0.4, 0.55, (150, 200, 140))]
    for px, py, w, h, c in pos:
        _rect(cv, cam, x + px - w / 2, py - h / 2, x + px + w / 2, py + h / 2, (250, 245, 230))
        _rect(cv, cam, x + px - w / 2 + 0.05, py - h / 2 + 0.05, x + px + w / 2 - 0.05, py + h / 2 - 0.05, c, _o(cam) * 0.4)
        _ell(cv, cam, x + px, py + 0.04, w * 0.18, w * 0.18, (255, 255, 255), 0)
    _rect(cv, cam, x - 0.9, 1.5, x + 0.9, 1.56, (130, 90, 60))                         # raf
    for k, c in enumerate([(200, 80, 80), (80, 140, 200), (230, 190, 70), (90, 170, 110)]):
        _rect(cv, cam, x - 0.8 + k * 0.2, 1.56, x - 0.64 + k * 0.2, 1.56 + 0.22 + 0.04 * (k % 2), c, _o(cam) * 0.5)
    _ell(cv, cam, x + 0.6, 1.66, 0.09, 0.1, (240, 190, 90))
    lx = x - 3.3                                                                        # abajur (sıcak ışık)
    _rect(cv, cam, x + lx - 0.03, 0.0, x + lx + 0.03, 1.25, (90, 80, 70))
    _poly(cv, cam, [(x + lx - 0.28, 1.25), (x + lx + 0.28, 1.25), (x + lx + 0.16, 1.62), (x + lx - 0.16, 1.62)], (255, 224, 140))
    _poly(cv, cam, [(x + 3.1, 0.0), (x + 3.1, 2.5), (x + 3.5, 2.5), (x + 3.4, 0.0)], (190, 90, 100), _o(cam) * 0.6)  # perde


PIECES = {
    "park_slide_zone": [(slide, 1.55)], "park_rules_sign": [(rules_sign, 0.0)], "park_trash_walk": [(bins, 1.3)],
    "park_flower_bed": [(flower_bed, 0.0)], "park_bike_pedestrian": [(bike_lane, 0.0)], "park_entrance": [(gate, 0.0)],
    "park_family_area": [(picnic, -0.2)], "home_kitchen": [(wall_decor, 0.0), (kitchen, 0.0)], "home_entry_corridor": [(wall_decor, 0.0), (corridor, 0.0)], "home_salon": [(wall_decor, 0.0), (salon, 0.0)],
}


def draw(cv, cam, loc, t=0.0):
    for fn, x in PIECES.get(loc or "", []):
        fn(cv, cam, x, t)
