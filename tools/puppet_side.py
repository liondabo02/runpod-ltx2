"""Yan (profil) görünüş rig'i. Ön görünüşte yatay esnetme tam dönüş sayılmaz; bu modül gerçek profil çizer:
burun çıkıntısı, tek göz, tek kulak, yan gövde, ön/arka kol, yürüyüşte ayaklar dünya konumunda (ön görünüşle aynı pose alanları).
Seçim: puppet2d.view_of(pose). Yön: yüzün baktığı taraf pose['yaw'] işaretinden gelir; sol bakış = sağ bakışın aynası (ayaklar hariç, onlar dünya koordinatı)."""
import math

SIDE_THRESHOLD = 0.95        # |gövde dönüşü| bu değerden büyükse profil


# profil yüzü yerleşimi (baş genişliği/yüksekliği katı; + yüzün baktığı yön)
EYE_U, NOSE_U, NOSE_V, EAR_U, MOUTH_U = 0.23, 0.49, 0.13, 0.20, 0.27


def _lids(emo, ex, ey, erx, ery, d):
    """Gözün üst ve alt sınırı: x -> y. Mutlu yüzde alt kapak ortada yukarı kabarır; üzgün/kızgın/sinsi yüzde üst kapak iner."""
    u = lambda x: max(-1.0, min(1.0, (x - ex) / erx))
    top = lambda x: ey - 2.0 * ery
    bot = lambda x: ey + 2.0 * ery
    if emo in ("happy", "laugh"):
        bot = lambda x: ey + ery * (0.62 - 0.24 * (1.0 - u(x) ** 2))
    elif emo == "sad":                       # arka köşe daha düşük
        top = lambda x: ey - ery * (0.38 + 0.22 * u(x) * d)
    elif emo == "angry":                     # ön köşe daha düşük
        top = lambda x: ey - ery * (0.34 - 0.24 * u(x) * d)
    elif emo == "sly":
        top = lambda x: ey - ery * 0.16
    return top, bot


def _clipped(cv, cx, cy, rx, ry, top, bot, n=36):
    """Elips noktaları üst/alt kapak sınırına kırpılır: dış çizgi kapağı izler, kopuk çizik kalmaz."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        pts.append((x, min(bot(x), max(top(x), y))))
    return pts


def _brow(emo, ex, ey, erx, ery, d, raise_):
    """Profil kaşı: [arka uç, orta, ön uç]. Eğim ve yükseklik ifadeye göre."""
    back, front, arch = {"happy": (-0.28, -0.24, -0.30), "laugh": (-0.20, -0.30, -0.26), "curious": (-0.12, -0.85, -0.18),
                         "surprise": (-0.62, -0.62, -0.34), "scared": (-0.40, -0.80, -0.10), "sad": (0.22, -0.55, 0.0),
                         "angry": (-0.30, 0.42, 0.0), "sly": (-0.35, 0.18, 0.0)}.get(emo, (0.0, 0.06, -0.06))
    y0 = ey - ery * 1.42 - ery * 0.35 * raise_
    x0, x1 = ex - d * erx * 1.0, ex + d * erx * 1.15
    return [(x0, y0 + back * ery), ((x0 + x1) / 2, y0 + (back + front) / 2 * ery + arch * ery), (x1, y0 + front * ery)]


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
    cr = P.crouch_of(des, pose) * ppm
    hip_y = by - leg_h + cr; torso_bot = hip_y - sit
    torso_top = torso_bot - torso_h * sq_
    lean = pose.get("lean", 0.0) * torso_h * 0.5 * d                      # ileri eğilme yüz yönüne
    head_cy = torso_top - head_h * 0.40 + pose["head"][0] * head_h * 0.06
    hx = fx + lean + d * head_w * 0.06
    wx = lambda dx: fx + d * dx                                           # yüz yönüne göre ileri ofset
    P.ground_shadow(cv, fx, fy, Hh, jump)

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
        if cr > 0.5 and sit <= 1 and lw != "skirt":                        # bükülü bacak: diz yüz yönüne
            ankle = (foot[0], foot[1] - Hh * 0.025); knee = P._knee(top, ankle, leg_h, d)
            col_ = lc if lw == "pants" else skin
            cv.capsule(top, knee, Hh * 0.054, Hh * 0.048, shade(col_, k), INK, ow); cv.capsule(knee, ankle, Hh * 0.048, Hh * 0.043, shade(col_, k), INK, ow)
            if lw != "pants":
                cv.capsule(top, ((top[0] + knee[0]) / 2, (top[1] + knee[1]) / 2), Hh * 0.056, Hh * 0.052, shade(shorts, k), INK, ow)
        elif lw == "pants":
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
    if "nose" not in st.get("hide", ()):
        cv.ellipse(hx + d * head_w * NOSE_U, head_cy + head_h * NOSE_V, head_w * 0.065, head_h * 0.065, skin, INK, ow)  # burun: gözün altında ve önünde
        cv.ellipse(hx + d * head_w * (NOSE_U - 0.040), head_cy + head_h * NOSE_V, head_w * 0.048, head_h * 0.046, skin, None, 0)  # iç çizgi silinir: yüze bağlı çıkıntı
    # kulak: gözün gerisinde, ince çizgili ve iç kıvrımlı (yüz ortasında ikinci bir ağız gibi okunmasın)
    ear_x, ear_y = hx - d * head_w * EAR_U, head_cy + head_h * 0.04
    cv.ellipse(ear_x, ear_y, head_w * 0.055, head_h * 0.085, shade(skin, 0.93), P.face_line(skin, shade(skin, 0.55)), ow * 0.45)
    inner = cv.arc_pts(ear_x, ear_y, head_w * 0.026, head_h * 0.046, math.pi * 0.5, math.pi * 1.5, 12)
    cv.line(inner if d > 0 else [(2 * ear_x - x_, y_) for x_, y_ in inner], P.face_line(skin, shade(skin, 0.55)), ow * 0.35)
    # ---- yüz: tek göz, kaş, ağız (ifade ön görünüşle aynı kurallarla: kapaklar, kaş eğimi/kalkışı, ağız biçimi, bakış)
    emo = st.get("emotion", "neutral")
    es_ = des.get("eye_scale", 1.0) * (0.84 if cls == "adult" else 1.0)
    erx, ery = head_w * 0.10 * es_, head_h * 0.17 * es_
    ex_, ey_ = hx + d * head_w * EYE_U, head_cy - head_h * 0.04
    rest_ery = ery                                                          # saç/şapka penceresi ifadeden bağımsız
    if emo in ("surprise", "scared"):
        erx *= 1.12; ery *= 1.22
    hide = st.get("hide", ())
    if "eyes" in hide:
        pass
    elif st.get("blink") or (emo == "laugh" and not st.get("eyes_open")):
        shut = cv.arc_pts(ex_, ey_ + ery * 0.1, erx, ery * 0.6, math.pi * 1.1, math.pi * 1.9) if emo == "laugh" else \
            [(ex_ - erx, ey_ + ery * 0.15), (ex_ + erx, ey_ + ery * 0.15)]
        cv.line(shut, P.face_line(skin, INK), ow * 1.2)
    else:
        top, bot = _lids(emo, ex_, ey_, erx, ery, d)
        cv.poly(_clipped(cv, ex_, ey_, erx, ery, top, bot), (255, 255, 255), INK, ow * 0.45)
        pr = erx * (0.46 if emo in ("surprise", "scared") else 0.66)
        gz = max(-1.0, min(1.0, float(st.get("gaze", 0.0)) * d))             # artı: yüzün baktığı yöne
        px_, py_ = ex_ + d * erx * (0.26 + 0.10 * gz), ey_ + ery * 0.08
        cv.poly(_clipped(cv, px_, py_, pr, pr * 1.2, top, bot), des["iris"], None, 0)
        cv.poly(_clipped(cv, px_, py_, pr * 0.55, pr * 0.7, top, bot), (15, 10, 15), None, 0)
        if emo in ("happy", "laugh", "sad", "angry", "sly"):                 # kapak çizgisi: kesik göz biçimi kopuk değil
            edge = bot if emo in ("happy", "laugh") else top
            xs = [ex_ + erx * k_ / 8.0 for k_ in range(-7, 8)]
            half = lambda x_: ery * math.sqrt(max(0.0, 1.0 - ((x_ - ex_) / erx) ** 2))
            line_ = [(x_, edge(x_)) for x_ in xs if abs(edge(x_) - ey_) < half(x_)]
            if len(line_) > 1:
                cv.line(line_, INK, ow * 0.8)
    limit = P.window_top(ey_, rest_ery, ow)
    hw_limit = P.headwear_edge(ey_, rest_ery, ow * 0.9, ow)
    style_, acc_ = des["hair_style"], des.get("accessory")
    brow_pts = _brow(emo, ex_, ey_, erx, ery, d, float(st.get("brow", 0.0)))
    ml = st.get("mouth", "X")
    if emo == "laugh" and ml == "X": ml = "D"
    if "mouth" not in hide:
        mx_, my_ = hx + d * head_w * MOUTH_U, head_cy + head_h * 0.27
        mw_, mh_ = head_w * 0.22 * des.get("mouth_w", 1.0), head_h * 0.16
        lw_ = max(1.0, ow / 4.5)                                             # büyük çizimde ağız çizgisi incecik kalmasın
        if ml == "X" and emo == "curious":                                   # merak: aralık küçük ağız (profilde yalnız kaş okunmuyor)
            cv.ellipse(mx_ + d * mw_ * 0.10, my_ + mh_ * 0.10, mw_ * 0.17, mh_ * 0.24, (110, 30, 45), P.face_line(skin, INK), 2.6 * lw_)
        else:
            P.draw_mouth(cv, mx_, my_, mw_, mh_, ml, P.face_line(skin, INK), emo, skin=skin, lw=lw_)
    # ---- ön saç
    if species != "hedgehog" and style not in ("bald", "hijab"):
        pts = cv.arc_pts(hx - d * head_w * 0.02, head_cy, head_w * 0.53, head_h * 0.54, math.pi, 2 * math.pi, 24)
        if d < 0: pts = pts[::-1]                                         # sola bakışta çokgen yönü ters çevrilir
        fr = [(hx + d * head_w * 0.50, head_cy - head_h * 0.16), (hx + d * head_w * 0.30, head_cy - head_h * 0.33),
              (hx + d * head_w * 0.05, head_cy - head_h * 0.25), (hx - d * head_w * 0.35, head_cy - head_h * 0.05), (hx - d * head_w * 0.54, head_cy - head_h * 0.10)]
        # öndeki köşeler pencere çizgisinin üstünde; ense saçı (arkadakiler) yerinde kalır
        poly_ = [(x_, min(y_, limit) if d * (x_ - hx) > -head_w * 0.05 and i_ >= len(pts) else y_) for i_, (x_, y_) in enumerate(pts + fr)]
        cv.poly(poly_, hair, INK, ow)
        if style == "bun":
            cv.ellipse(hx - d * head_w * 0.18, head_cy - head_h * 0.56, head_w * 0.16, head_w * 0.15, hair, INK, ow)
        if style == "ponytail":
            cv.ellipse(hx - d * head_w * 0.62, head_cy + head_h * 0.10, head_w * 0.12, head_h * 0.30, hair, INK, ow, rot=0.3 * d)
    if style == "hijab":
        sc = des.get("scarf", hair)
        # yüz açıklığı olan örtü: ense -> tepe -> alın, sonra gözün üstünden ve gerisinden çeneye (ileri yön = d)
        u = lambda uu, y_: (hx + d * head_w * uu, y_)
        outer = [u(0.58 * math.cos(a_), head_cy - head_h * 0.02 + head_h * 0.57 * math.sin(a_)) for a_ in (math.pi * (0.88 + 0.90 * i_ / 24) for i_ in range(25))]
        brim = min(hw_limit, head_cy - head_h * 0.36)
        inner = [u(0.36, brim), u(0.08, min(limit, head_cy - head_h * 0.24)), u(-0.01, head_cy + head_h * 0.08),
                 u(0.12, head_cy + head_h * 0.44), u(0.10, head_cy + head_h * 0.60), u(-0.40, head_cy + head_h * 0.60)]
        cv.poly(outer + inner, sc, INK, ow * 0.9)
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
        gw, gh = max(erx * 1.5, erx + ow * 1.2), max(ery * 1.25, ery + ow * 1.2)       # küçük gözde de çerçeve çizgisi gözün üstüne binmez
        cv.line(cv.arc_pts(ex_, ey_, gw, gh, 0, 2 * math.pi, 28), INK, ow)
        cv.line([(ex_ - d * gw, ey_), (hx - d * head_w * 0.10, ey_ - ery * 0.1)], INK, ow * 0.8)
    elif acc == "beanie":
        cv.poly(P.dome(cv, hx, head_cy - head_h * 0.02, head_w * 0.54, head_h * 0.64, math.pi, 2 * math.pi, hw_limit), des["accent"], INK, ow)
    elif acc == "hat":                                                     # tepe kenarlığın üstünde (düz disk gibi görünmesin)
        brim_y = min(top + head_h * 0.08, hw_limit - head_h * 0.06)
        cv.poly(cv.arc_pts(hx, brim_y, head_w * 0.42, head_h * 0.36, math.pi, 2 * math.pi, 20), des["accent"], INK, ow)
        cv.ellipse(hx + d * head_w * 0.10, brim_y, head_w * 0.62, head_h * 0.06, shade(des["accent"], 0.85), INK, ow)
    elif acc == "bow":
        cv.ellipse(hx - d * head_w * 0.30, top + head_h * 0.12, head_w * 0.12, head_w * 0.08, des["accent"], INK, ow)
    elif acc == "flower_pin":
        fr_ = head_w * 0.075
        for k_ in range(5):
            a_ = k_ * 2 * math.pi / 5
            cv.ellipse(hx - d * head_w * 0.10 + math.cos(a_) * fr_ * 0.8, head_cy + head_h * 0.30 + math.sin(a_) * fr_ * 0.8, fr_ * 0.55, fr_ * 0.55, (255, 214, 60), INK, ow * 0.5)
    if "brows" not in hide:                                              # saç ve şapkadan sonra
        covered = style_ != "bald" or species == "hedgehog" or acc_ in ("hat", "beanie", "glasses")
        over_ = covered and min(y_ for _x, y_ in brow_pts) - ow * 0.45 < limit
        bw_ = ow * (1.5 if emo != "neutral" else 1.2) * des.get("brow_w", 1.0)
        cv.line(brow_pts, P.brow_colour(INK, P.cover_colours(des), skin, over_), bw_)
    return {"head": (hx, head_cy), "nose_x": hx + d * head_w * 0.58}


def hand_offset(des, pose, side):
    """Profilde elin ayağa göre konumu (metre): (dx dünya x, yükseklik). draw_profile.arm ile aynı geometri."""
    Hh = des["height"]; cls = des["class"]
    leg_h = Hh * {"infant": 0.20, "toddler": 0.24, "child": 0.28, "adult": 0.38}[cls]
    torso_h = Hh * {"infant": 0.22, "toddler": 0.25, "child": 0.27, "adult": 0.30}[cls]
    d = facing(pose); sq_ = float(pose.get("sq", 1.0))
    jump = pose["z"]; sit = max(0.0, -pose["z"])
    import puppet2d as _P
    torso_top = -jump - leg_h - sit - torso_h * sq_ + _P.crouch_of(des, pose)
    lean = pose.get("lean", 0.0) * torso_h * 0.5 * d
    fwd, out = pose["aL"] if side == "L" else pose["aR"]
    ang = max(-1.2, min(2.6, -fwd * 0.9 + abs(out) * 0.35))
    ln = Hh * 0.27 * (1.0 - 0.22 * min(1.0, abs(fwd) / 1.3))
    shx, shy = lean * 0.8, torso_top + torso_h * 0.16
    return shx + d * math.sin(ang) * ln, -(shy + math.cos(ang) * ln)
