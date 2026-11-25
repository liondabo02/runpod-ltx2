"""Yan (profil) görünüş rig'i. Ön görünüşte yatay esnetme tam dönüş sayılmaz; bu modül gerçek profil çizer:
burun çıkıntısı, tek göz, tek kulak, yan gövde, ön/arka kol, yürüyüşte ayaklar dünya konumunda (ön görünüşle aynı pose alanları).
Seçim: puppet2d.view_of(pose). Yön: yüzün baktığı taraf pose['yaw'] işaretinden gelir; sol bakış = sağ bakışın aynası (ayaklar hariç, onlar dünya koordinatı)."""
import math

SIDE_THRESHOLD = 0.95        # |gövde dönüşü| bu değerden büyükse profil


def facing(pose):
    y = pose.get("yaw", 0.0)
    return 1.0 if y >= 0 else -1.0


def draw_profile(cv, des, pose, st, fx, fy, ppm, t, P):
    """P: puppet2d modülü (INK, shade, draw_mouth). Döner: {'head':(x,y), 'face_x':baktığı yöne burun ucu x}."""
    INK, shade = P.INK, P.shade
    Hh = des["height"] * ppm; cls = des["class"]
    leg_h = Hh * {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}[cls]
    torso_h = Hh * {"infant": 0.22, "toddler": 0.25, "child": 0.27, "adult": 0.30}[cls]
    head_h = Hh - leg_h - torso_h + Hh * 0.05; head_w = head_h * 1.0
    torso_w = Hh * {"infant": 0.30, "toddler": 0.28, "child": 0.25, "adult": 0.22}[cls] * des.get("build", 1.0) * 0.90
    ow = max(3.0, Hh * 0.019)
    skin, shirt, shorts, hair = des["skin"], des["shirt"], des["shorts"], des["hair"]
    d = facing(pose)
    jump = pose["z"] * ppm; sit = max(0.0, -pose["z"]) * ppm
    by = fy - jump
    sq_ = float(pose.get("sq", 1.0))
    hip_y = by - leg_h; torso_bot = hip_y - sit
    torso_top = torso_bot - torso_h * sq_
    lean = pose.get("lean", 0.0) * torso_h * 0.5 * d                      # ileri eğilme yüz yönüne
    head_cy = torso_top - head_h * 0.40 + pose["head"][0] * head_h * 0.06
    hx = fx + lean + d * head_w * 0.06
    wx = lambda dx: fx + d * dx                                           # yüz yönüne göre ileri ofset

    # ---- uzak kol (gövdenin arkasında, koyu)
    def arm(side, near):
        fwd, out = pose["aL"] if side == "L" else pose["aR"]
        ang = max(-1.2, min(2.6, -fwd * 0.9 + abs(out) * 0.35))
        ln = Hh * 0.27 * (1.0 - 0.22 * min(1.0, abs(fwd) / 1.3))
        sh = (fx + lean * 0.8, torso_top + torso_h * 0.16)
        hand = (sh[0] + d * math.sin(ang) * ln, sh[1] + math.cos(ang) * ln)
        k = 1.0 if near else 0.82
        cv.capsule(sh, hand, Hh * 0.034, Hh * 0.029, shade(skin, k), INK, ow)
        mid = (sh[0] + (hand[0] - sh[0]) * 0.42, sh[1] + (hand[1] - sh[1]) * 0.42)
        cv.capsule(sh, mid, Hh * 0.043, Hh * 0.039, shade(shirt, k), INK, ow)
        cv.ellipse(hand[0], hand[1], Hh * 0.046, Hh * 0.044, shade(skin, k), INK, ow * 0.9)
    # ---- bacaklar (arka bacak koyu), ayaklar dünya konumunda
    for side, near in (("R", False), ("L", True)):
        swing = pose["lL"] if side == "L" else pose["lR"]
        top = (fx + lean * 0.2, torso_bot - torso_h * 0.03)
        if ("f" + side) in pose:
            foot = (fx + pose["f" + side] * Hh, fy - Hh * 0.01 - pose["h" + side] * Hh - max(0, jump))
        else:
            foot = (fx + d * swing * leg_h * 0.28, fy - Hh * 0.01 - max(0.0, swing) * leg_h * 0.28 - max(0, jump))
        if sit > 1:
            foot = (fx + d * leg_h * 0.7, fy - Hh * 0.01)
            top = (fx, torso_bot)
        k = 1.0 if near else 0.80
        lw = des.get("lowerwear", "shorts"); lc = des.get("lower_color", shorts)
        if lw == "pants":
            cv.capsule(top, (foot[0], foot[1] - Hh * 0.025), Hh * 0.054, Hh * 0.045, shade(lc, k), INK, ow)
        elif lw != "skirt":
            cv.capsule(top, (foot[0], foot[1] - Hh * 0.03), Hh * 0.042, Hh * 0.038, shade(skin, k), INK, ow)
            cv.capsule(top, ((top[0] + foot[0]) / 2, (top[1] + foot[1]) / 2 - Hh * 0.01), Hh * 0.052, Hh * 0.048, shade(shorts, k), INK, ow)
        cv.ellipse(foot[0] + d * Hh * 0.05, foot[1], Hh * 0.085, Hh * 0.038, shade(des["accent"], 0.9 * k), INK, ow)
        if side == "R":
            arm("R", False)                                               # uzak kol bacağın üstünde, gövdenin altında kalır
    # ---- gövde (yandan: dar, hafif eğri)
    tw = torso_w
    pts = [(fx + lean - tw * 0.5, torso_top + torso_h * 0.10), (fx + lean - tw * 0.3, torso_top), (fx + lean + tw * 0.3, torso_top),
           (fx + lean + tw * 0.5, torso_top + torso_h * 0.12), (fx + tw * 0.55, torso_bot), (fx - tw * 0.55, torso_bot)]
    cv.poly_cel(pts, shirt, INK, ow)
    if des.get("lowerwear") == "skirt":
        cv.poly([(fx - tw * 0.55, torso_bot - torso_h * 0.10), (fx + tw * 0.55, torso_bot - torso_h * 0.10),
                 (fx + tw * 1.15, by - Hh * 0.05), (fx - tw * 1.15, by - Hh * 0.05)], shirt, INK, ow)
    else:
        cv.poly([(fx - tw * 0.55, torso_bot - torso_h * 0.14), (fx + tw * 0.55, torso_bot - torso_h * 0.14), (fx + tw * 0.55, torso_bot), (fx - tw * 0.55, torso_bot)],
                des.get("lower_color", shorts), None, 0)
    # ---- yakın kol gövdenin önünde
    arm("L", True)
    # ---- boyun + arka saç
    cv.capsule((fx + lean, torso_top + 2), (hx - d * head_w * 0.04, torso_top - head_h * 0.12), Hh * 0.03, Hh * 0.03, skin, INK, ow)
    style, species = des["hair_style"], des["species"]
    if species == "hedgehog":
        for i in range(8):
            a = math.radians(95 + i * 18) if d > 0 else math.radians(85 - i * 18)
            c0 = (hx - d * head_w * 0.30, head_cy - head_h * 0.15 + i * head_h * 0.07)
            tip = (c0[0] - d * head_w * (0.55 + 0.08 * (i % 2)), c0[1] + head_h * 0.10)
            cv.poly([(c0[0], c0[1] - head_h * 0.07), tip, (c0[0], c0[1] + head_h * 0.07)], hair, INK, ow * 0.8)
    if style in ("wavy_long", "curly", "ponytail", "bob", "hijab"):
        L = {"wavy_long": 0.95, "curly": 0.65, "ponytail": 0.70, "bob": 0.40, "hijab": 0.80}[style]
        col = des.get("scarf", hair) if style == "hijab" else hair
        cv.poly([(hx - d * head_w * 0.05, head_cy - head_h * 0.30), (hx - d * head_w * 0.58, head_cy - head_h * 0.10),
                 (hx - d * head_w * 0.62, head_cy + head_h * L * 0.75), (hx - d * head_w * 0.20, head_cy + head_h * L * 0.55),
                 (hx + d * head_w * 0.12, head_cy + head_h * 0.15)], col, INK, ow)
    # ---- kafa (yandan: oval + yüz yönünde burun çıkıntısı)
    cv.ellipse_cel(hx, head_cy, head_w * 0.50, head_h * 0.52, skin, INK, ow, k=0.86)
    cv.ellipse(hx + d * head_w * 0.47, head_cy + head_h * 0.08, head_w * 0.065, head_h * 0.065, skin, INK, ow)          # burun
    cv.ellipse(hx - d * head_w * 0.10, head_cy + head_h * 0.12, head_w * 0.06, head_h * 0.09, shade(skin, 0.86), INK, ow * 0.55)   # kulak
    # ---- yüz: tek göz, kaş, ağız
    emo = st.get("emotion", "neutral")
    es_ = des.get("eye_scale", 1.0) * (0.84 if cls == "adult" else 1.0)
    erx, ery = head_w * 0.10 * es_, head_h * 0.17 * es_
    ex_, ey_ = hx + d * head_w * 0.27, head_cy - head_h * 0.04
    if st.get("blink") or emo == "laugh":
        cv.line([(ex_ - erx, ey_ + ery * 0.15), (ex_ + erx, ey_ + ery * 0.15)], INK, ow * 1.2)
    else:
        cv.ellipse(ex_, ey_, erx, ery, (255, 255, 255), INK, ow * 0.45)
        pr = erx * (0.50 if emo in ("surprise", "scared") else 0.66)
        cv.ellipse(ex_ + d * erx * 0.30, ey_ + ery * 0.08, pr, pr * 1.2, des["iris"], None, 0)
        cv.ellipse(ex_ + d * erx * 0.30, ey_ + ery * 0.08, pr * 0.55, pr * 0.7, (15, 10, 15), None, 0)
    cv.line([(ex_ - d * erx * 0.9, ey_ - ery * 1.45), (ex_ + d * erx * 1.1, ey_ - ery * (1.35 if emo != "surprise" else 1.9))], INK, ow * 0.9)
    ml = st.get("mouth", "X")
    if emo == "laugh" and ml == "X": ml = "D"
    P.draw_mouth(cv, hx + d * head_w * 0.36, head_cy + head_h * 0.27, head_w * 0.17 * des.get("mouth_w", 1.0), head_h * 0.15, ml, INK, emo)
    # ---- ön saç
    if species != "hedgehog" and style not in ("bald", "hijab"):
        pts = cv.arc_pts(hx - d * head_w * 0.02, head_cy, head_w * 0.53, head_h * 0.54, math.pi, 2 * math.pi, 24)
        if d < 0: pts = pts[::-1]                                         # sola bakışta çokgen yönü ters çevrilir
        fr = [(hx + d * head_w * 0.50, head_cy - head_h * 0.16), (hx + d * head_w * 0.30, head_cy - head_h * 0.33),
              (hx + d * head_w * 0.05, head_cy - head_h * 0.25), (hx - d * head_w * 0.35, head_cy - head_h * 0.05), (hx - d * head_w * 0.54, head_cy - head_h * 0.10)]
        cv.poly(pts + fr, hair, INK, ow)
        if style == "bun":
            cv.ellipse(hx - d * head_w * 0.18, head_cy - head_h * 0.56, head_w * 0.16, head_w * 0.15, hair, INK, ow)
        if style == "ponytail":
            cv.ellipse(hx - d * head_w * 0.62, head_cy + head_h * 0.10, head_w * 0.12, head_h * 0.30, hair, INK, ow, rot=0.3 * d)
    if style == "hijab":
        sc = des.get("scarf", hair)
        cv.poly(cv.arc_pts(hx, head_cy - head_h * 0.02, head_w * 0.58, head_h * 0.57, math.pi * 0.95, 2.05 * math.pi, 26) +
                [(hx + d * head_w * 0.30, head_cy + head_h * 0.30), (hx - d * head_w * 0.3, head_cy + head_h * 0.40)], sc, INK, ow * 0.9)
    # ---- aksesuar
    acc = des.get("accessory"); top = head_cy - head_h * 0.50
    if acc == "star":
        cx_, cy_, r_ = hx - d * head_w * 0.10, top + head_h * 0.14, head_w * 0.12
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5; rr = r_ if i % 2 == 0 else r_ * 0.45
            pts.append((cx_ + math.cos(a) * rr, cy_ + math.sin(a) * rr))
        cv.poly(pts, (255, 214, 60), INK, ow * 0.7)
    elif acc == "glasses":
        cv.line(cv.arc_pts(ex_, ey_, erx * 1.5, ery * 1.25, 0, 2 * math.pi, 28), INK, ow)
        cv.line([(ex_ - d * erx * 1.5, ey_), (hx - d * head_w * 0.10, ey_ - ery * 0.1)], INK, ow * 0.8)
    elif acc in ("hat", "beanie"):
        bc = des["accent"]
        cv.poly(cv.arc_pts(hx, head_cy - head_h * 0.02, head_w * 0.54, head_h * 0.55, math.pi, 2 * math.pi, 24), bc, INK, ow)
        if acc == "hat":
            cv.ellipse(hx + d * head_w * 0.10, top + head_h * 0.08, head_w * 0.62, head_h * 0.09, shade(bc, 0.85), INK, ow)
    elif acc == "bow":
        cv.ellipse(hx - d * head_w * 0.30, top + head_h * 0.12, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
    elif acc == "flower_pin":
        fr_ = head_w * 0.075
        for k_ in range(5):
            a_ = k_ * 2 * math.pi / 5
            cv.ellipse(hx - d * head_w * 0.10 + math.cos(a_) * fr_ * 0.8, head_cy + head_h * 0.30 + math.sin(a_) * fr_ * 0.8, fr_ * 0.55, fr_ * 0.55, (255, 214, 60), INK, ow * 0.5)
    return {"head": (hx, head_cy), "nose_x": hx + d * head_w * 0.58}
