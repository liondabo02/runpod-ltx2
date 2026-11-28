"""AHOS çekim hareket mantığı (saf Python, Blender'dan bağımsız; testlenebilir).

Bir vuruşun eylem metninden her karakter için hareket türü seçer, zamana bağlı poz üretir.
Açı konvansiyonu (mesh_factory yüzü -Y'ye bakar):
  kol/bacak 'rx' negatif = ileri; kol 'ry' dışarı: sağ(R) -a, sol(L) +a;
  kafa rx pozitif = öne eğ; root lean pozitif = öne eğil; yaw pozitif = -Y'den +X'e dön.
"""
import math, re

W = 2 * math.pi
MOVE_FADE_S = 0.2        # yürüyüşe özgü ek salınımların açılma süresi (sn)
SWAY_IN_S = 1.5          # bekleme/bakınma salınımı bu sürede açılır: plan başında çizilen konum = plan durumu

KINDS = [  # öncelik sırasıyla (ilk eşleşen kazanır)
    ("run", r"koş|kaç|fırla|süzül\w* hız"),
    ("jump", r"zıpla|atla|sıçra|hoplay"),
    ("dance", r"dans|dönüp|dön(er|erek|üyor)|sallan"),
    ("wave", r"salla|selam|karşıla|el sal"),
    ("laugh", r"gül|kahkaha|eğlen|neşe"),
    ("surprise", r"şaşır|ürk|korku|hayret|irkil|aniden"),
    ("sit", r"otur|çömel"),
    ("reach", r"kaldır|topla|uzan|koy(ar|up|du)|sula|al(ır|ıp|dı|arak)\b|tut(ar|up|ar)|yakal|çek(er|ip)|kaz|dök|ek(er|ip|ti)\b|çukur|eğil|uzat|göster|işaret"),
    ("look", r"ara(r|rlar|ken|yıp|mak)?\b|bak|gör|keşfet|incele|dinle|izle"),
    ("walk", r"yürü|git|gider|gel|yaklaş|ilerle|in(er|ip)\b|dolaş|takip|çık|geç|tırman|süzül|yuvarlan|peşin"),
]
KIND_RE = [(k, re.compile(p, re.I)) for k, p in KINDS]
SPEED = {"run": 3.0, "walk": 1.6, "carry": 1.4}


def classify(text):
    t = (text or "").lower()
    for kind, rx in KIND_RE:
        if rx.search(t):
            return kind
    return "idle"


def clauses(text):
    return [c.strip() for c in re.split(r"[.;!?]|,| ve | ama | sonra ", text or "") if c.strip()]


def motion_for(char, action, char_name=None, seed=0):
    """Eylem metninde karakterin adı geçen cümleciğe göre hareket türü; yoksa genel eylem."""
    key = (char_name or char or "").lower()[:3]
    if key:
        for c in clauses(action):
            if key in c.lower():
                k = classify(c)
                if k != "idle":
                    return k
    k = classify(action)
    return k


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def slots(n, spread=1.25):
    if n <= 1:
        return [0.0]
    return [round((i - (n - 1) / 2.0) * spread, 3) for i in range(n)]


def move_target(kind, x0, seed):
    d = 1.0 if (seed % 2 == 0) else -1.0
    dist = {"walk": 1.8, "run": 2.9}.get(kind, 0.0)
    x1 = x0 + d * dist
    if abs(x1) > 1.9:
        x1 = x0 - d * dist
    return max(-1.9, min(1.9, x1))


def base_pose(x=0.0):
    return {"x": x, "y": 0.0, "z": 0.0, "yaw": 0.0, "lean": 0.0,
            "head": [0.0, 0.0, 0.0], "aL": [0.0, 0.0], "aR": [0.0, 0.0], "lL": 0.0, "lR": 0.0}


def arm_out(p, side, a):
    (p["aL"] if side == "L" else p["aR"])[1] = (a if side == "L" else -a)


def arm_fwd(p, side, a):
    (p["aL"] if side == "L" else p["aR"])[0] = -a


def blend_arm(p, side, out, fwd, w):
    """Kolu o anki açılarından (w=0) verilen dışa/öne açıya (w=1) sürekli geçirir."""
    a = p["aL"] if side == "L" else p["aR"]
    a[1] += ((out if side == "L" else -out) - a[1]) * w
    a[0] += (-fwd - a[0]) * w


try:
    import style_profile as _stp
except Exception:       # profil yoksa varsayılan davranış
    _stp = None


IDLE_ARM_BASE, IDLE_ARM_LIFT = 0.12, 0.36       # boşta kıpırtının kol açısı (radyan): el gevşek kalır (puppet2d.REST_ARM_ANG altı)
IDLE_ARM_BLEND = 0.5                            # boşta kıpırtı kolu, kıpırtı şiddeti bu değere varana kadar o anki pozdan açılır
ACCENT_BLEND = 0.12                             # konuşma vurgusu kolu, vurgu penceresinin (0..0,5) bu kadarlık iki ucunda açılır/döner
JUMP_PUSH, JUMP_ARM = 0.25, 0.40                # zıplamada itişin ve kol savurmasının/indirmesinin havada kalma içindeki payı
SURPRISE_HOLD_S, SURPRISE_DIP_S = 0.25, 0.14    # şaşırmanın tepe tutma süresi ve hazırlık çömelmesi (sn)
PLANTED = ("idle", "look")                      # ayakları yerde duran eylemler: gövde ağırlık aktarır, ayaklar eylemin işaretinde kalır (render2d)
IDLE_SHIFT_K, LOOK_SHIFT_K = 0.05, 0.04         # ağırlık aktarımı genliği (boy oranı): ayaklar yerindeyken bacakların okunur kaldığı aralık
LOOK_TURN = 0.35                                # bakınırken yön değiştirme: salınım hızı bu oranın altındayken baş/gövde yumuşakça öbür yana döner
# ---- yürüyüşü kesen tepki: fren + iki adımda durma
BRAKE_S = 0.30                                  # fren süresi (sn); durma mesafesi sınırlanırsa kısalır
BRAKE_MIN_S = 0.15
STOP_MAX_K = 0.12                               # fren mesafesi en çok boyun bu oranı (geride kalan basılı ayak bacağın erişiminde kalır)
STOP_STEP_S, GATHER_STEP_S = 0.20, 0.22         # ilk adım (havadaki / arkadaki ayak) ve toplama adımı süreleri (sn)
STOP_LIFT_K = 0.045                             # durma adımında ayağın kalkma yüksekliği (boy oranı)


# ---------------------------------------------------------------- ayak izleri (birim: bir adım çevrimi boyu D; konum = gidilen yol)
# Her salınım (p0, p1, hedef): ayak, gövde p0 yolundayken kalkar, p1'de 'hedef' noktasına basar; arada kalan her yerde bastığı noktada SABİTTİR.
# Basışlar yarım adım arayla dizilir (0.5, 1.0, ... n): ardışık iki basış arası hiç yarım adımı geçmez, ayak gövdeden en çok ±stance/2 uzaklaşır.
# Yürüyüş duruş pozunda (iki ayak da gövdenin altında, 0) başlar; ilk adım yarım boydur, sonuncusu geride kalan ayağı hedefte toplar.
STANCE = {"walk": 0.62, "run": 0.38}      # bir ayağın çevrim içinde yerde kaldığı oran
FIRST_LIFT, LAST_LAND = 0.02, 0.02        # ilk kalkış yoldan bu kadar sonra, son basış hedeften bu kadar önce (D)
ARM_SWING_K = 0.85             # ön / üç-çeyrek yürüyüş: ayakların açıklığı (boy oranı) başına kolun ekran yönünde salınım açısı
ARM_SWING_MAX = 0.22           # en büyük salınım açısı (radyan): daha büyüğünde iki el gövde önünde üst üste biner (el çırpma gibi okunur)
STRIDE_STRETCH_MAX = 1.2       # yol tam sayıda çevrime bölünürken adım doğal boyunun en çok bu katına uzar
LIFT_MIN_STEP = 0.35           # kısa toplama adımında ayak en az tam kaldırmanın bu oranı kadar kalkar
BOB_FADE = 0.25                # adım yaylanması yolun bu ilk/son parçasında (D) açılır/söner


def stride_count(total, d0):
    n = max(1, round(total / d0))
    return n + 1 if total / n > STRIDE_STRETCH_MAX * d0 else n


def footsteps(gait, n):
    """n çevrimlik yürüyüşün salınımları: {'R': [(p0, p1, hedef)], 'L': [...]}; ilk adımı R atar. Her iki ayak 0'da başlar, n'de biter."""
    stance = STANCE[gait]; a = stance / 2.0; swing = 1.0 - stance
    out = {"R": [], "L": []}
    for m in range(1, 2 * n + 1):                          # m'inci basış: 0.5*m noktasına, gövde oraya a kala
        land = 0.5 * m - a
        out["R" if m % 2 else "L"].append((FIRST_LIFT if m == 1 else land - swing, land, 0.5 * m))
    out["R"].append((n - 0.5 + a, n - LAST_LAND, float(n)))      # toplama adımı
    return out


def foot_at(swings, p):
    """p yolundayken ayağın (konum, kaldırma 0..1, atılan adımın boyu). Basılıyken kaldırma tam 0."""
    at = 0.0
    for p0, p1, to in swings:
        if p <= p0 + 1e-9:
            break
        if p < p1 - 1e-9:
            u = (p - p0) / (p1 - p0)
            r0, r1 = at - p0, to - p1                      # gövdeye göre kalkış ve basış uzaklığı: salınım ikisinin arasında kalır
            return p + r0 + (r1 - r0) * (0.5 - 0.5 * math.cos(math.pi * u)), math.sin(math.pi * u), to - at
        at = to
    return at, 0.0, 0.0


def sway_envelope(t, dur):
    """Bekleme/bakınma ağırlık aktarımı eylem işaretinde başlar ve orada biter: sonraki plan ayakların durduğu yerden sürer."""
    return smooth(t / SWAY_IN_S) * smooth((dur - t) / SWAY_IN_S)


def pose_at(kind, t, dur, seed, x0, x1, H, hip_z, speaking=False):
    prof = _stp.current() if _stp else {"gait": True, "speak_acting": True, "energy": 1.0}
    carry = (kind == "carry")                          # nesne taşıyarak yürüme: yürüyüş + kollar önde, daha ağır adım
    if carry:
        kind = "walk"
    p = base_pose(x0)
    p["sq"] = 1.0
    ph = 0.0 if dur <= 0 else min(1.0, max(0.0, t / dur))
    s = (seed % 7) * 0.9
    for side in "LR":
        arm_out(p, side, 0.10 + 0.03 * math.sin(W * 0.4 * t + s))
    p["z"] = 0.012 * H * abs(math.sin(W * 0.9 * t + s))
    p["head"][2] = 0.25 * math.sin(W * 0.35 * t + s)
    p["head"][1] = 0.10 * math.sin(W * 0.5 * t + s * 1.3)
    p["yaw"] = 0.12 * math.sin(W * 0.2 * t + s)
    p["lean"] = 0.03 * math.sin(W * 0.45 * t + s)
    for side, sg in (("L", 1), ("R", -1)):
        arm_fwd(p, side, 0.25 * (0.5 + 0.5 * math.sin(W * 0.7 * t + s + sg)))

    if kind in ("walk", "run"):
        f = SPEED[kind]; amp = 0.5 if kind == "walk" else 0.95
        kid = (H < 1.25) and prof.get("gait", True)                                   # çocuk: kısa, hızlı, sekmeli adım; yetişkin: uzun, ağır adım
        pers = (seed % 4) if prof.get("gait", True) else 0                                  # 0 normal, 1 caka (arkaya yaslı, omuz sallar), 2 sürtünerek/ağır, 3 zıp zıp
        if kid: f *= 1.3; amp *= 0.9
        if pers == 2: f *= 0.8; amp *= 0.7
        if pers == 3: f *= 1.1
        # EVRELER: hazırlık (geri çekil, çömel, gövdeyi yöne çevir) → ana aksiyon → toparlanma (aşma, yaylanma, yüz yönü dönüşü).
        # Süreler boya, kişiliğe ve hıza göre değişir (çocuk kısa/çevik, ağır yürüyüş uzun, koşu daha uzun hazırlanır ve durur).
        run_ = (kind == "run")
        te = 0.85 * dur
        ta = (0.26 if kind == "run" else 0.16) * (0.8 if kid else 1.0) * (1.35 if pers == 2 else 1.0)
        tr = (0.50 if kind == "run" else 0.30) * (0.85 if kid else 1.0) * (1.3 if pers == 2 else 1.0)
        ta = min(ta, 0.2 * te); tr = min(tr, max(0.05, dur - te))
        mv = smooth((t - ta) / max(1e-6, te - ta))
        p["x"] = x0 + (x1 - x0) * mv
        direction = 1.0 if x1 >= x0 else -1.0
        if t < ta:
            yaw_k = 0.2 + (0.60 if run_ else 0.55) * smooth(t / ta)    # gövde gidilecek yöne dönmeye başlar
        elif t < te:
            yaw_k = 0.80 if run_ else 0.75                       # koşu: tam profil, yürüyüş: üç-çeyrek
        else:
            yaw_k = 0.2 + (0.60 if run_ else 0.55) * (1.0 - smooth((t - te) / tr))  # durunca yüzünü sahneye çevirir
        p["yaw"] = direction * yaw_k
        p["view"] = "side" if yaw_k * 1.25 >= 0.95 else ("three_quarter" if yaw_k * 1.25 >= 0.45 else "front")   # görünüş, adım salınımından bağımsız (kare kare titremez)
        # ADIM = KAT EDİLEN MESAFE: temas eden ayak dünyada sabit kalır (ayak kayması yok). Faz süreden değil gidilen yoldan gelir.
        run_ = (kind == "run")
        D0 = (1.05 if run_ else 0.62) * H * (0.88 if kid else 1.0) * (0.85 if pers == 2 else 1.0)      # doğal adım çevrimi (sol+sağ) boyu, m
        total = abs(x1 - x0)
        n_cyc = stride_count(total, D0) if total > 1e-6 else 0
        D = total / n_cyc if n_cyc else D0                                                          # yol, tam sayıda çevrime bölünür
        dpath = abs(p["x"] - x0)
        steps = footsteps("run" if run_ else "walk", n_cyc) if n_cyc else {"L": [], "R": []}
        for key in "LR":
            at, up, size = foot_at(steps[key], dpath / D)
            lf = up * (0.18 if run_ else 0.10) * H * max(LIFT_MIN_STEP, min(1.0, size)) * min(1.0, D / D0)
            p["f" + key] = direction * (at * D - dpath) / H          # gövdeye göre, H'ye oran (puppet piksele çevirir); duruşta 0
            p["h" + key] = lf / H
        p["planted"] = True                                  # ayaklar yola bağlı ve sürekli: poz geçişi eski ayağı karıştırmaz (basılı ayak sürüklenmez)
        if not carry:                                                                       # kol, aynı yandaki ayakla ters fazda; duruşta kendiliğinden 0
            a_sw = max(-ARM_SWING_MAX, min(ARM_SWING_MAX, ARM_SWING_K * (p["fR"] - p["fL"])))
            p["swL"], p["swR"] = a_sw, -a_sw
        sw = math.sin(W * (dpath / D))                                                      # kol/bacak salınımı (ayaklarla ters kol)
        env = smooth(min(dpath, n_cyc * D - dpath) / (BOB_FADE * D)) if n_cyc else 0.0
        bob = env * abs(math.cos(W * (dpath / D)))                                          # gövde ayak yerden geçerken yüksek, çift basışta alçak
        p["lL"], p["lR"] = -amp * sw, amp * sw
        for side, sg in (("L", 1), ("R", -1)):
            arm_fwd(p, side, sg * amp * 0.7 * sw + (0.5 if kind == "run" else 0.0))
            arm_out(p, side, 0.12)
        p["z"] = bob * (0.02 if kind == "walk" else 0.07) * H
        dip = 0.03 if kind == "walk" else 0.07
        p["sq"] = 1.0 - dip * (env - bob)                                                # adım temasında hafif ezilme; dururken yok
        p["lean"] = 0.04 if kind == "walk" else 0.20
        run_k = 1.0 if run_ else 0.5
        if t < ta:                                           # hazırlık: geri yaslan, çömel, kollar geri — sonra bırakılır
            a_ant = smooth(t / ta)
        else:
            a_ant = math.exp(-(t - ta) / 0.22)
        p["lean"] -= 0.12 * run_k * a_ant; p["sq"] -= 0.05 * run_k * a_ant
        if not carry:
            for k_ in ("aL", "aR"):
                p[k_][0] += 0.45 * run_k * a_ant              # kollar geriye (arm_fwd'un tersi, eklemeli)
        if t >= te:                                          # toparlanma: ileri aşma, gövde yaylanması, kol/baş takibi
            u = min(1.0, (t - te) / tr)
            p["lean"] = p["lean"] * (1.0 - smooth(u)) - 0.07 * run_k * math.sin(math.pi * u)
            p["sq"] = 1.0 - 0.06 * run_k * math.sin(math.pi * u)
            p["head"][0] += 0.10 * run_k * math.sin(math.pi * u)
            if not carry:
                for k_ in ("aL", "aR"):
                    p[k_][0] -= 0.45 * run_k * math.sin(math.pi * u) * (1.0 - u)   # kollar öne savrulur, yatışır
        if carry:
            for side_ in "LR":
                arm_fwd(p, side_, 0.95); arm_out(p, side_, 0.30)
            p["lean"] = -0.05; p["head"][0] += 0.10
        # yürürken eklenen salınım ve duruş farkı: hareket başında açılır, durunca toparlanma süresinde söner (tek karede açılıp kapanmaz)
        mk = smooth((t - ta) / MOVE_FADE_S) * (1.0 - smooth((t - te) / tr))
        if mk > 0.0:
            p["z"] += mk * bob * H * ((0.025 if kid else 0.0) + (0.03 if pers == 3 else 0.0))     # sekme
            p["yaw"] += mk * direction * 0.07 * sw * (2.0 if pers == 1 else 1.0)                                # omuz/kalça salınımı
            p["head"][2] += mk * 0.12 * math.sin(W * f * t) * (1.6 if pers == 1 else 1.0)                     # baş adımla yalpalar
            p["head"][0] += mk * (0.22 if pers == 2 else (-0.08 if pers == 1 else 0.0))                          # ağır: başı öne; caka: yukarı
            p["lean"] += mk * (-0.07 if pers == 1 else (0.08 if pers == 2 else 0.0))
    elif kind == "wave":
        pre = smooth(min(1.0, t / 0.35))                  # hazırlık: kol önce hafif aşağıdan gelir
        arm_out(p, "R", (2.4 + 0.35 * math.sin(W * 2.5 * t)) * pre)
        p["lean"] = -0.05 * (1.0 - pre)
        p["head"][1] = 0.12; p["yaw"] = 0.15 * math.sin(W * 0.3 * t)
    elif kind == "jump":
        cyc = (ph * 3.0) % 1.0
        j = max(0.0, math.sin(math.pi * min(1.0, max(0.0, (cyc - 0.22) / 0.62))))        # havada kalma
        p["z"] = 0.22 * H * j
        if cyc < 0.22:                                   # HAZIRLIK: çömel, kollar önceki inişten geriye
            c = smooth(cyc / 0.22)
            p["sq"] = 1.0 - 0.16 * c; p["lean"] = 0.10 * c
            for side_ in "LR":
                arm_out(p, side_, 0.5 - 0.3 * c); arm_fwd(p, side_, -0.6 * c)
        elif cyc < 0.84:                                 # HAVA: uzama, kollar yukarı savrulur ve inişe iner (evre sınırlarında poz sürekli)
            u = (cyc - 0.22) / 0.62
            push = 1.0 - smooth(u / JUMP_PUSH)           # hazırlık çömelmesinin kalanı itişte açılır
            p["sq"] = 1.0 + 0.10 * j - 0.16 * push; p["lean"] = 0.10 * push
            for side_ in "LR":
                arm_out(p, side_, 0.2 + 2.3 * smooth(u / JUMP_ARM) - 2.0 * smooth((u - (1.0 - JUMP_ARM)) / JUMP_ARM))
                arm_fwd(p, side_, -0.6 * push)
            p["lL"] = p["lR"] = 0.25 * j
        else:                                            # İNİŞ: ezilme + sekme
            c = math.sin(math.pi * (cyc - 0.84) / 0.16)
            p["sq"] = 1.0 - 0.14 * c; p["lean"] = 0.08 * c
            arm_out(p, "L", 0.5); arm_out(p, "R", 0.5)
    elif kind == "dance":
        p["z"] = 0.03 * H * abs(math.sin(W * 2 * t))
        p["yaw"] = 0.5 * math.sin(W * 1.0 * t)
        arm_out(p, "L", 1.4 + 0.8 * math.sin(W * 1.0 * t)); arm_out(p, "R", 1.4 - 0.8 * math.sin(W * 1.0 * t))
        p["lL"] = 0.3 * math.sin(W * 2 * t); p["lR"] = -p["lL"]
        p["head"][1] = 0.25 * math.sin(W * 1.0 * t)
    elif kind == "laugh":
        p["z"] = 0.015 * H * math.sin(W * 6 * t)
        p["head"][0] = -0.3; p["lean"] = -0.08
        arm_fwd(p, "L", 0.5); arm_fwd(p, "R", 0.5)
    elif kind == "surprise":
        k = math.exp(-3.0 * max(0.0, t - SURPRISE_HOLD_S))      # tepe, pozdan poza geçiş bitene kadar korunur, sonra söner
        if t < SURPRISE_DIP_S:                                  # önce küçük çömelme, sonra uzama: ikisi de sıfırdan sürekli
            p["sq"] = 1.0 - 0.10 * math.sin(math.pi * t / SURPRISE_DIP_S)
        else:
            p["sq"] = 1.0 + 0.12 * k * smooth((t - SURPRISE_DIP_S) / SURPRISE_DIP_S)
        p["z"] = 0.12 * H * k
        arm_out(p, "L", 0.3 + 1.6 * k); arm_out(p, "R", 0.3 + 1.6 * k)
        p["head"][0] = -0.15 * k; p["lean"] = -0.12 * k
    elif kind == "sit":
        sit = smooth(ph / 0.2)
        p["z"] = -max(0.0, hip_z - 0.06 * H) * sit
        p["lL"] = p["lR"] = -1.45 * sit
        arm_fwd(p, "L", 0.4 * sit); arm_fwd(p, "R", 0.4 * sit)
    elif kind == "reach":
        b = math.sin(math.pi * smooth(ph))
        p["lean"] = 0.38 * b
        arm_fwd(p, "L", 1.2 * b); arm_fwd(p, "R", 1.2 * b)
        p["head"][0] = 0.25 * b
    elif kind == "look":
        p["head"][2] = 0.9 * math.sin(W * 0.4 * t + s)
        p["head"][0] = 0.18; p["lean"] = 0.12 + 0.05 * math.sin(W * 0.8 * t)
        p["x"] = x0 + LOOK_SHIFT_K * H * math.sin(W * 0.12 * t + s) * sway_envelope(t, dur)      # ağırlık aktarır; yer değiştirmez (adımsız gezinme yok)
        arm_fwd(p, "L", 0.6 + 0.3 * math.sin(W * 0.9 * t)); arm_out(p, "R", 0.5)
        turn = max(-1.0, min(1.0, math.cos(W * 0.12 * t + s) / LOOK_TURN))
        p["yaw"] = 0.5 * math.sin(0.5 * math.pi * turn)                        # öbür yana dönüş sürekli (tek karede ters dönmez)
    # konuşurken doğal el/baş hareketi (yalnız sakin türlerde)
    if speaking and kind in ("idle", "look", "wave", "sit"):
        g = 0.5 + 0.5 * math.sin(W * 1.7 * t + s)
        p["head"][0] += 0.07 * math.sin(W * 3 * t)
        if kind != "wave":
            arm_fwd(p, "R", 0.9 * g); arm_out(p, "R", 0.35 + 0.5 * g)
        p["z"] += 0.02 * H * max(0.0, math.sin(W * 2.3 * t))
    # konuşma oyunculuğu: nefes alma, vurgu jesti (baş onayı + el), tepki
    if speaking and prof.get("speak_acting", True) and kind not in ("walk", "run", "jump", "dance", "laugh", "surprise", "reach"):
        if t < 0.18:                                     # konuşmadan önce küçük nefes: hafif geriye + yukarı
            k_ = math.sin(math.pi * t / 0.18)
            p["lean"] -= 0.05 * k_; p["z"] += 0.012 * H * k_
        slot = int(t // 1.3); loc = (t % 1.3) / 1.3
        h2 = ((slot * 2246822519 + seed * 3266489917) & 0xFFFF) / 65535.0
        if h2 > 0.45 and loc < 0.5:                      # vurgu: baş vurur, bir el yukarı-öne açılır
            e = math.sin(math.pi * loc / 0.5)
            side = "R" if h2 > 0.72 else "L"
            en = prof.get("energy", 1.0)
            w_ = smooth(min(loc, 0.5 - loc) / ACCENT_BLEND)       # vurgu pozu o anki koldan açılır ve ona döner (tek karede atlamaz)
            blend_arm(p, side, 0.4 + 0.9 * e * en, 0.6 * e * en, w_)
            if e > 0.55:                                  # vurgu tepesinde jest eli: işaret / yumruk / başparmak (kişiliğe göre)
                g_ = (None, "fist", "thumb")[int(h2 * 7) % 3]      # işaret parmağı rastgele seçilmez: gösterme hedefi olan veridir (pointing)
                if g_:
                    p["hand"], p["hand_side"] = g_, side
            p["head"][0] += 0.16 * e; p["lean"] += 0.04 * e; p["sq"] = p.get("sq", 1.0) + 0.01 * e
    # canlılık katmanı: bekleyen karakter de yaşar (ağırlık kaydırma, ara sıra jest, merak)
    if kind in ("idle", "look", "sit"):
        slot = int(t // 3.2); loc = (t % 3.2) / 3.2
        h = ((slot * 2654435761 + seed * 40503) & 0xFFFF) / 65535.0
        bump = math.sin(math.pi * min(1.0, loc / 0.45)) if loc < 0.45 else 0.0
        if kind != "sit":
            p["x"] += IDLE_SHIFT_K * H * math.sin(W * 0.11 * t + s) * sway_envelope(t, dur)   # ağırlık kaydırma (işaretten açılır, işarete döner)
        if h > 0.55:                                  # boşta kıpırtı: kol hafifçe açılır; yataya yakın kalkmaz (hedefsiz 'gösterme' gibi okunuyordu)
            side = "R" if h > 0.78 else "L"
            blend_arm(p, side, IDLE_ARM_BASE + IDLE_ARM_LIFT * bump, 0.4 * bump, smooth(bump / IDLE_ARM_BLEND))
            p["head"][2] += 0.3 * bump * (1 if h > 0.78 else -1)
        elif h < 0.2:                                 # kafa eğ, düşün
            p["head"][2] += 0.35 * bump; p["lean"] += 0.05 * bump
        p["z"] += 0.01 * H * max(0.0, math.sin(W * 1.3 * t + s))
    return p


def segment(m, lt, dur):
    """Plan içi hareket parçası: (hareket sözlüğü, yerel zaman, parça süresi).
    'approach' varsa karakter önce önceki planın bittiği yerden ('from') eylem işaretine (x0) YÜRÜR, eylem varınca başlar.
    Çizim, ön kontrol ve süreklilik aynı fonksiyonu kullanır (iki ayrı konum hesabı yok)."""
    ap = m.get("approach")
    if ap:
        ws = float(ap["walk_s"])
        if lt < ws:
            return dict(m, kind="walk", x0=float(ap["from"]), x1=float(m["x0"]), walk_s=ws), lt, ws
        return m, lt - ws, max(0.1, dur - ws)
    if m.get("kind") == "walk" and m.get("walk_s"):      # yerleşim çözücü: temastan önce varacak yürüyüş süresi
        return m, lt, float(m["walk_s"])
    return m, lt, dur


def halt_info(m, dur, H):
    """Yürüyüş ortasında gelen yönetmen tepkisi (m['halt_t']): o anki hız ve ayaklardan frenleme planı; yürümüyorsa None.
    Beden kalan hızıyla kısa mesafede durur; havadaki (yoksa arkadaki) ayak durma noktasına basar, öbürü bu sırada BASILI kalır,
    sonra toplanır. Hiçbir ayak yerdeyken sürüklenmez. Boy ve yöne göre türetilir; projeye özel sabit yok."""
    th = m.get("halt_t")
    if th is None:
        return None
    s, t_, d_ = segment(m, float(th), dur)
    if s["kind"] not in ("walk", "run", "carry") or abs(float(s.get("x1", s["x0"])) - float(s["x0"])) < 0.02:
        return None
    at = lambda u: pose_at(s["kind"], max(0.0, u), d_, s.get("seed", 0), s["x0"], s["x1"], H, H * 0.45)
    now = at(t_)
    xr = now["x"]
    v0 = (at(t_ + 1e-3)["x"] - at(t_ - 1e-3)["x"]) / (t_ + 1e-3 - max(0.0, t_ - 1e-3))
    way = 1.0 if s["x1"] >= s["x0"] else -1.0
    dist = min(abs(v0) * BRAKE_S / 2.0, STOP_MAX_K * H, abs(float(s["x1"]) - xr))
    brake = max(BRAKE_MIN_S, 2.0 * dist / abs(v0)) if abs(v0) > 1e-3 else BRAKE_MIN_S
    feet = {k: (xr + now.get("f" + k, 0.0) * H, now.get("h" + k, 0.0) * H) for k in "LR"}
    first = max("LR", key=lambda k: (round(feet[k][1], 4), -way * feet[k][0]))
    return {"xr": xr, "stop": xr + way * dist, "brake": brake, "feet": feet, "first": first, "H": H}


def halt_x(info, tau):
    u = min(1.0, max(0.0, tau / info["brake"]))
    return info["xr"] + (info["stop"] - info["xr"]) * (2.0 * u - u * u)


def halt_feet(info, tau):
    """Frenden tau sn sonra ayaklar: {'L'|'R': (dünya x, yükseklik m)}."""
    H, stop, out = info["H"], info["stop"], {}
    for k in "LR":
        a, h = info["feet"][k]
        first = k == info["first"]
        t0, span = (0.0, STOP_STEP_S) if first else (STOP_STEP_S, GATHER_STEP_S)
        u = min(1.0, max(0.0, (tau - t0) / span))
        e = smooth(u)
        far = abs(stop - a) / H
        lift = STOP_LIFT_K * H * max(0.35, min(1.0, far / 0.08)) if far > 0.01 else 0.0
        rest = h * (1.0 - smooth(tau / STOP_STEP_S))                    # kalkık ayak ilk adım süresinde yere iner
        out[k] = (a + (stop - a) * e, rest + lift * math.sin(math.pi * u))
    return out


def motion_x(m, lt, dur, H):
    """Plan içi lt anında karakterin dünya x konumu (tepki/uzanma bindirmeleri hariç taban hareket)."""
    if m.get("halt_t") is not None and lt > float(m["halt_t"]):
        info = halt_info(m, dur, H)
        if info:
            return halt_x(info, lt - float(m["halt_t"]))
    s, t_, d_ = segment(m, lt, dur)
    return pose_at(s["kind"], t_, d_, s.get("seed", 0), s["x0"], s["x1"], H, H * 0.45)["x"]


def mark_halt(motion, react):
    """Yönetmen tepkisi yürüyüş değilse oyuncunun yürüyüşü o anda frenlenir: taban hareket verisine 'halt_t' yazılır.
    Planlayıcı, yerleşim çözücüler, süreklilik ve çizim aynı konumu okur (iki ayrı konum hesabı yok)."""
    for cid, m in motion.items():
        rc = (react or {}).get(cid)
        if rc and rc.get("kind") not in ("walk", "run", "carry"):
            m["halt_t"] = float(rc["t"])
        else:
            m.pop("halt_t", None)


def reaction_dur(kind, t_react, dur):
    """Tepki hareketinin süresi. Ayakları basılı bekleme/bakınma tepkisi plan sonunda işaretine döner (kalan süre); diğerleri planın süresi."""
    return max(0.1, dur - t_react) if kind in PLANTED else dur


def exit_x(m, dur, H, react=None):
    """Plan SONUNDA çizilen konum. react: {'t','kind'} yönetmen tepkisi (o andan sonra tepki hareketi, konum plan boyunca taban hareketten)."""
    x = motion_x(m, dur, dur, H)
    if react and dur >= float(react["t"]):
        left = dur - float(react["t"])
        x = pose_at(react["kind"], left, reaction_dur(react["kind"], float(react["t"]), dur), m.get("seed", 0), x, x, H, H * 0.45)["x"]
    return x


def entry_x(m):
    """Plan BAŞINDA karakterin konumu."""
    ap = m.get("approach")
    return float(ap["from"]) if ap else float(m["x0"])


VISEME_OPEN = {"X": 0.05, "A": 0.12, "B": 0.40, "C": 0.85, "D": 1.0, "E": 0.65, "F": 0.35, "G": 0.30, "H": 0.60}


def mouth_open(cues, t_in_line):
    for c in cues:
        if c[0] <= t_in_line < c[1]:
            return c[2]
    return 0.05


def blink(t, seed):
    ph = (t + seed * 0.37) % 3.6
    return 1.0 if ph < 0.12 else 0.0


CAMS = {"wide": (5.2, 1.2, 0.85, 30.0), "medium": (3.4, 1.0, 0.8, 35.0), "close": (2.2, 1.0, 0.8, 50.0)}


def camera_for(preset, cx, focus_h, beat_index, ph):
    dist, cz, tz, lens = CAMS.get(preset, CAMS["medium"])
    if preset == "close":
        tz = focus_h * 0.80; cz = tz + 0.05
    off = (0.5 if beat_index % 2 == 0 else -0.5) * (1.0 if preset == "wide" else 0.5)
    d = dist * (1.0 - 0.08 * ph)
    return {"loc": [cx + off, -d, cz], "target": [cx, 0.0, tz], "lens": lens}
