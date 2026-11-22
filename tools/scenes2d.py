"""AHOS 2D boyalı arka planlar (garden / roof / room). Saf Pillow, kamera: (cx, cy, zoom)."""
import math, random
from puppet2d import W, H, INK, BASE_PPM, shade, lerp


class Cam:
    def __init__(self, cx, cy, zoom):
        self.cx, self.cy, self.z = cx, cy, zoom
        self.s = BASE_PPM * zoom

    def x(self, wx, p=1.0):
        return W / 2 + (wx - self.cx * p) * self.s

    def y(self, wy):
        return H / 2 + (self.cy - wy) * self.s


def gradient(cv, top, bot, y0=0, y1=H):
    n = 36
    for i in range(n):
        c = tuple(int(lerp(top[k], bot[k], i / (n - 1))) for k in range(3))
        ya, yb = lerp(y0, y1, i / n), lerp(y0, y1, (i + 1) / n)
        cv.poly([(0, ya), (W, ya), (W, yb + 1), (0, yb + 1)], c, None, 0)


def hills(cv, cam, base_y, amp, col, p, seed, t=0):
    rnd = random.Random(seed)
    ph = [rnd.random() * 6 for _ in range(3)]
    pts = [(0, H)]
    for sx in range(-20, W + 40, 20):
        wx = (sx - W / 2) / cam.s + cam.cx * p
        h = amp * (0.6 + 0.4 * math.sin(wx * 0.35 + ph[0]) + 0.25 * math.sin(wx * 0.9 + ph[1]))
        pts.append((sx, cam.y(base_y + h)))
    pts.append((W + 40, H))
    cv.poly(pts, col, None, 0)


def tree(cv, cam, wx, base_y, h, p, ow, light=1.0):
    x, yb = cam.x(wx, p), cam.y(base_y)
    s = cam.s
    tw = 0.16 * s * 0.5
    th = h * 0.55
    cv.poly([(x - tw, yb), (x - tw * 0.7, yb - th * s), (x + tw * 0.7, yb - th * s), (x + tw, yb)], (150, 105, 70), INK, ow)
    r = h * s * 0.36
    cy = yb - th * s - r * 0.35
    for dx, dy, k in ((-0.55, 0.15, 0.80), (0.55, 0.12, 0.80), (0.0, -0.1, 1.0)):
        cv.ellipse(x + dx * r, cy + dy * r, r * k, r * k * 0.92, (70, 160, 85), INK, ow)
    cv.ellipse(x - 0.28 * r, cy - 0.35 * r, r * 0.55, r * 0.4, (110, 195, 110), None, 0)
    cv.ellipse(x + 0.35 * r, cy + 0.45 * r, r * 0.5, r * 0.28, (50, 130, 70), None, 0)


def flower(cv, cam, wx, wy, col, t, size=1.0):
    x, y = cam.x(wx), cam.y(wy)
    s = cam.s
    sw = math.sin(t * 1.6 + wx * 2.1) * 0.02 * s
    top = (x + sw, y - 0.22 * s * size)
    cv.line([(x, y), top], (60, 140, 70), max(2, 0.012 * s))
    for k in range(5):
        a = k * 2 * math.pi / 5 + 0.4
        cv.ellipse(top[0] + math.cos(a) * 0.04 * s * size, top[1] + math.sin(a) * 0.04 * s * size, 0.035 * s * size, 0.035 * s * size, col, INK, 1.6)
    cv.ellipse(top[0], top[1], 0.026 * s * size, 0.026 * s * size, (255, 220, 90), INK, 1.4)


def bush(cv, cam, wx, wy, r, ow):
    x, y = cam.x(wx), cam.y(wy)
    s = cam.s
    for dx, dy, k in ((-0.7, 0.1, 0.8), (0.7, 0.1, 0.8), (0, -0.25, 1.0)):
        cv.ellipse(x + dx * r * s, y + dy * r * s, r * s * k, r * s * k * 0.85, (60, 150, 75), INK, ow)
    cv.ellipse(x - 0.2 * r * s, y - 0.45 * r * s, r * s * 0.5, r * s * 0.32, (105, 190, 105), None, 0)


def _stage(cv, cam, t, ow):
    """Stand-up/tiyatro sahnesi: tuğla duvar, spot ışığı, perde, tahta zemin."""
    gradient(cv, (70, 30, 40), (110, 50, 55))
    s = cam.s; fy = cam.y(1.3)
    cx = cam.x(0.0)
    for i in range(7):                             # spot ışığı (alfa yerine açılan halkalar)
        k = i / 6.0
        cv.ellipse(cx, fy - 1.1 * s, (1.7 - 1.2 * k) * s, (1.3 - 0.9 * k) * s, (int(105 + 55 * k), int(55 + 45 * k), int(58 + 30 * k)), None, 0)
    for r in range(int(H // (0.3 * s)) + 2):      # tuğlalar
        y = r * 0.3 * s
        cv.line([(0, y), (W, y)], (60, 26, 34), 2)
        off = 0.0 if r % 2 else 0.45 * s
        x = off
        while x < W:
            cv.line([(x, y), (x, y + 0.3 * s)], (60, 26, 34), 2); x += 0.9 * s
    gradient(cv, (120, 78, 48), (86, 54, 34), fy, H)   # tahta zemin
    for i in range(-14, 16):
        x = cam.x(i * 0.8)
        cv.line([(x, fy), (x - 0.5 * s, H)], (64, 40, 26), 2)
    cv.poly([(0, fy), (W, fy), (W, fy + 6), (0, fy + 6)], INK, None, 0)
    for sg in (-1, 1):                             # kırmızı perdeler
        x0 = W / 2 + sg * (W / 2 - 0.55 * s)
        for j in range(5):
            xa = x0 + sg * j * 0.2 * s
            cv.poly([(xa, 0), (xa + sg * 0.2 * s, 0), (xa + sg * 0.2 * s, fy), (xa, fy)], (150 - j % 2 * 30, 25, 40), INK, ow * 0.6)
    cv.ellipse(cam.x(-3.3), cam.y(3.0), 0.16 * s, 0.16 * s, (255, 225, 120), INK, ow)   # sahne lambaları
    cv.ellipse(cam.x(3.3), cam.y(3.0), 0.16 * s, 0.16 * s, (255, 225, 120), INK, ow)


def _village(cv, cam, t, ow):
    """Köy/mahalle sokağı: gökyüzü, tepeler, renkli evler, çit, taş yol."""
    gradient(cv, (120, 190, 245), (230, 245, 255))
    s = cam.s
    cv.ellipse(cam.x(-4, 0.1), cam.y(3.3), 0.7 * s, 0.7 * s, (255, 238, 150), None, 0)
    hills(cv, cam, 1.45, 0.35, (130, 195, 120), 0.3, 3, t)
    cols = [(230, 120, 100), (240, 200, 90), (120, 170, 220), (200, 140, 200), (140, 200, 150)]
    for i in range(-6, 7):
        wx = i * 1.5; hh = 0.65 + ((i * 7) % 3) * 0.15
        x0, x1 = cam.x(wx, 0.6), cam.x(wx + 1.0, 0.6); yb = cam.y(0.62); yt = cam.y(0.62 + hh)
        cv.poly([(x0, yb), (x0, yt), (x1, yt), (x1, yb)], cols[i % 5], INK, ow)
        cv.poly([(x0 - 0.1 * s, yt), ((x0 + x1) / 2, yt - 0.32 * s), (x1 + 0.1 * s, yt)], (176, 82, 70), INK, ow)
        wx0 = x0 + 0.25 * (x1 - x0)
        cv.poly([(wx0, yt + 0.15 * s), (wx0 + 0.2 * s, yt + 0.15 * s), (wx0 + 0.2 * s, yt + 0.4 * s), (wx0, yt + 0.4 * s)], (255, 245, 190), INK, ow * 0.7)
    fy = cam.y(0.6)
    gradient(cv, (190, 165, 130), (150, 128, 98), fy, H)
    for r in range(4):                             # kaldırım taşları
        for c in range(-16, 17):
            x = cam.x(c * 0.6 + (0.3 if r % 2 else 0)); y = fy + (0.2 + r * 0.45) * s
            cv.ellipse(x, y, 0.26 * s, 0.1 * s, (165, 142, 112), None, 0)
    for i in range(-12, 13):                       # çit
        x = cam.x(i * 0.5)
        cv.poly([(x, fy - 0.45 * s), (x + 0.12 * s, fy - 0.45 * s), (x + 0.12 * s, fy), (x, fy)], (225, 200, 160), INK, ow * 0.6)


def scene_back(cv, kind, cam, t=0.0, seed=1):
    ow = max(1.6, 0.012 * cam.s)
    rnd = random.Random(seed)
    if kind == "stage":
        _stage(cv, cam, t, ow); return
    if kind == "village":
        _village(cv, cam, t, ow); return
    if kind == "garden":
        gradient(cv, (96, 176, 243), (205, 238, 255))
        cv.ellipse(cam.x(6.5, 0.1), cam.y(4.3), 0.55 * cam.s, 0.55 * cam.s, (255, 236, 130), None, 0)
        for i in range(5):
            wx = (i * 4.1 - 8 + t * 0.15) % 22 - 10
            cx, cy = cam.x(wx, 0.15), cam.y(3.2 + (i % 3) * 0.45)
            for dx, k in ((-0.5, 0.7), (0, 1.0), (0.55, 0.75)):
                cv.ellipse(cx + dx * cam.s * 0.5, cy, 0.38 * cam.s * k, 0.2 * cam.s * k, (255, 255, 255), None, 0)
        hills(cv, cam, 1.15, 0.5, (160, 212, 150), 0.25, 3)
        hills(cv, cam, 1.05, 0.35, (125, 196, 120), 0.45, 5)
        for i, wx in enumerate((-11, -7.5, -4.2, -1.0, 2.4, 5.8, 9.2, 12.5)):
            tree(cv, cam, wx + (i % 3) * 0.4, 1.05, 1.5 + (i % 3) * 0.3, 0.65, ow)
        gy = cam.y(1.1)
        gradient(cv, (118, 200, 92), (88, 168, 70), gy, H)
        for i in range(-12, 14):
            x = cam.x(i * 0.62)
            cv.poly([(x - 0.045 * cam.s, cam.y(0.65)), (x - 0.04 * cam.s, cam.y(1.35)), (x + 0.04 * cam.s, cam.y(1.4)), (x + 0.045 * cam.s, cam.y(0.65))], (246, 232, 205), INK, ow)
        for yy in (1.12, 0.9):
            cv.poly([(0, cam.y(yy)), (W, cam.y(yy)), (W, cam.y(yy - 0.07)), (0, cam.y(yy - 0.07))], (246, 232, 205), INK, ow)
        for i in range(70):
            gx = rnd.uniform(-10, 10); gyw = rnd.uniform(-0.8, 1.0)
            x, y = cam.x(gx), cam.y(gyw)
            cv.poly([(x - 0.03 * cam.s, y), (x, y - 0.09 * cam.s), (x + 0.03 * cam.s, y)], (78, 158, 62), None, 0)
        cols = [(255, 120, 130), (255, 215, 80), (210, 140, 235), (255, 255, 255)]
        for i in range(36):
            flower(cv, cam, rnd.uniform(-9, 9), rnd.uniform(-0.1, 1.0), cols[i % 4], t, 1.0)
    elif kind in ("path", "water"):
        dusk = kind == "path"
        gradient(cv, (150, 110, 200) if dusk else (110, 190, 245), (255, 190, 140) if dusk else (215, 240, 255))
        cv.ellipse(cam.x(-2.2, 0.1), cam.y(2.5), 0.7 * cam.s, 0.7 * cam.s, (255, 235, 170), None, 0)
        hills(cv, cam, 1.3, 0.7, (120, 100, 160) if dusk else (150, 205, 170), 0.2, 11)
        hills(cv, cam, 1.1, 0.45, (96, 140, 120) if dusk else (120, 190, 140), 0.4, 13)
        gy = cam.y(1.1)
        if dusk:
            gradient(cv, (110, 170, 100), (80, 140, 80), gy, H)
            cv.poly([(cam.x(-0.5), gy), (cam.x(0.9), gy), (cam.x(3.2), H), (cam.x(-4.2), H)], (226, 196, 150), INK, ow)
            for i in range(9):  # rüzgar çizgileri
                yy = cam.y(2.4 - i * 0.25); xx = cam.x(((i * 3.7 + t * 2.2) % 18) - 9)
                cv.line([(xx, yy), (xx + 1.2 * cam.s, yy - 0.05 * cam.s)], (255, 255, 255), max(2, int(ow)))
            for i, wx in enumerate((-3.6, -2.6, 3.4, 4.2)):
                tree(cv, cam, wx, 1.05, 1.6 + (i % 2) * 0.3, 0.6, ow)
        else:
            gradient(cv, (70, 160, 215), (40, 110, 175), gy, H)
            for i in range(14):
                wx = ((i * 1.9 + t * 0.4) % 16) - 8
                cv.line([(cam.x(wx), cam.y(0.8 - (i % 5) * 0.18)), (cam.x(wx + 0.5), cam.y(0.8 - (i % 5) * 0.18))], (230, 245, 255), max(2, int(ow)))
            for wx in (-3.2, 3.0):
                bush(cv, cam, wx, 1.0, 0.55, ow)
    elif kind == "roof":
        gradient(cv, (255, 140, 110), (255, 225, 170))
        cv.ellipse(cam.x(4, 0.1), cam.y(1.9), 0.9 * cam.s, 0.9 * cam.s, (255, 240, 190), None, 0)
        for i in range(24):
            wx = -12 + i * 1.1; hgt = 0.6 + ((i * 37) % 5) * 0.3
            x0, x1 = cam.x(wx, 0.3), cam.x(wx + 1.0, 0.3)
            cv.poly([(x0, cam.y(1.3)), (x0, cam.y(1.3 + hgt)), (x1, cam.y(1.3 + hgt)), (x1, cam.y(1.3))], (150, 95, 120), None, 0)
        gradient(cv, (170, 95, 78), (130, 70, 60), cam.y(1.25), H)
        for r in range(7):
            for c in range(-14, 15):
                x = cam.x(c * 0.5 + (0.25 if r % 2 else 0)); y = cam.y(1.15 - r * 0.28)
                cv.ellipse(x, y, 0.25 * cam.s, 0.09 * cam.s, (150, 82, 66), None, 0)
        x, yb = cam.x(-3.0), cam.y(1.2)
        cv.poly([(x - 0.4 * cam.s, yb), (x - 0.4 * cam.s, yb - 1.6 * cam.s), (x + 0.4 * cam.s, yb - 1.6 * cam.s), (x + 0.4 * cam.s, yb)], (190, 110, 90), INK, ow)
        for k in range(3):
            cv.ellipse(x + math.sin(t + k) * 0.1 * cam.s, yb - (1.9 + 0.4 * ((t * 0.5 + k * 0.33) % 1.0)) * cam.s, (0.14 + 0.03 * k) * cam.s, 0.1 * cam.s, (240, 230, 225), None, 0)
    else:
        gradient(cv, (250, 232, 198), (240, 215, 175))
        fy = cam.y(1.5)
        gradient(cv, (205, 150, 100), (165, 112, 72), fy, H)
        for i in range(-12, 14):
            x = cam.x(i * 0.7)
            cv.line([(x, fy), (x - 0.4 * cam.s, H)], (140, 95, 60), 2)
        cv.poly([(0, fy), (W, fy), (W, fy + 6), (0, fy + 6)], INK, None, 0)
        x, y = cam.x(2.0), cam.y(2.6)
        cv.poly([(x - 0.8 * cam.s, y), (x + 0.8 * cam.s, y), (x + 0.8 * cam.s, y + 1.3 * cam.s), (x - 0.8 * cam.s, y + 1.3 * cam.s)], (255, 255, 255), INK, ow * 1.6)
        cv.poly([(x - 0.7 * cam.s, y + 0.1 * cam.s), (x + 0.7 * cam.s, y + 0.1 * cam.s), (x + 0.7 * cam.s, y + 1.2 * cam.s), (x - 0.7 * cam.s, y + 1.2 * cam.s)], (160, 215, 250), None, 0)
        cv.line([(x, y + 0.1 * cam.s), (x, y + 1.2 * cam.s)], INK, ow)
        cv.line([(x - 0.7 * cam.s, y + 0.65 * cam.s), (x + 0.7 * cam.s, y + 0.65 * cam.s)], INK, ow)
        tx, ty = cam.x(-2.6), cam.y(1.2)
        cv.poly([(tx - 0.8 * cam.s, ty), (tx + 0.8 * cam.s, ty), (tx + 0.8 * cam.s, ty + 0.12 * cam.s), (tx - 0.8 * cam.s, ty + 0.12 * cam.s)], (160, 110, 70), INK, ow)
        for sg in (-1, 1):
            cv.poly([(tx + sg * 0.7 * cam.s - 0.05 * cam.s, ty + 0.12 * cam.s), (tx + sg * 0.7 * cam.s + 0.05 * cam.s, ty + 0.12 * cam.s), (tx + sg * 0.7 * cam.s + 0.05 * cam.s, ty + 0.9 * cam.s), (tx + sg * 0.7 * cam.s - 0.05 * cam.s, ty + 0.9 * cam.s)], (140, 95, 60), INK, ow)
        cv.ellipse(cam.x(0), cam.y(-0.25), 2.2 * cam.s, 0.45 * cam.s, (214, 90, 100), INK, ow)
        bx, by = cam.x(-3.4), cam.y(2.35)   # kitaplık
        cv.poly([(bx, by), (bx + 1.5 * cam.s, by), (bx + 1.5 * cam.s, by + 1.55 * cam.s), (bx, by + 1.55 * cam.s)], (176, 120, 78), INK, ow)
        pal = [(214, 90, 90), (90, 150, 214), (240, 200, 80), (110, 190, 120), (170, 110, 200)]
        for r in range(2):
            for c in range(6):
                hh = 0.4 + ((r * 7 + c * 3) % 3) * 0.05
                x0 = bx + 0.1 * cam.s + c * 0.22 * cam.s; y1 = by + (0.7 + r * 0.75) * cam.s
                cv.poly([(x0, y1), (x0 + 0.18 * cam.s, y1), (x0 + 0.18 * cam.s, y1 - hh * cam.s), (x0, y1 - hh * cam.s)], pal[(r + c) % 5], INK, ow * 0.6)
        tvx, tvy = cam.x(-0.9), cam.y(2.35)   # televizyon
        cv.poly([(tvx, tvy), (tvx + 1.3 * cam.s, tvy), (tvx + 1.3 * cam.s, tvy + 0.9 * cam.s), (tvx, tvy + 0.9 * cam.s)], (60, 70, 140), INK, ow)
        cv.poly([(tvx + 0.1 * cam.s, tvy + 0.1 * cam.s), (tvx + 1.2 * cam.s, tvy + 0.1 * cam.s), (tvx + 1.2 * cam.s, tvy + 0.8 * cam.s), (tvx + 0.1 * cam.s, tvy + 0.8 * cam.s)], (150, 205, 240), None, 0)


def birds(cv, cam, t):
    """Uzakta uçan kuşlar (yalnız dış mekânlar; hareketli arka plan = canlılık)."""
    for i in range(3):
        bx = ((t * (0.35 + 0.1 * i) + i * 3.1) % 14.0) - 7.0
        by = 3.4 + 0.3 * i + 0.12 * math.sin(t * 2 + i)
        x, y, w = cam.x(bx, 0.3), cam.y(by), 0.16 * cam.s
        fl = math.sin(t * 9 + i) * 0.5 * w
        cv.line([(x - w, y + fl), (x, y), (x + w, y + fl)], INK, max(2, int(0.02 * cam.s)))


def scene_front(cv, kind, cam, t=0.0):
    if kind in ("garden", "path", "water", "village"):
        birds(cv, cam, t)
    if kind in ("garden", "path", "water") and cam.z < 1.8:
        ow = max(1.6, 0.012 * cam.s)
        for wx, wy, r in ((-3.0, -0.95, 0.75), (3.1, -1.0, 0.7), (-4.8, -0.8, 0.5), (4.9, -0.8, 0.5)):   # ön plan katmanı (derinlik)
            bush(cv, cam, wx, wy, r, ow)
