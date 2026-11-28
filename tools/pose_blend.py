"""AHOS poz geçişi (diziden bağımsız, saf Python): oyuncunun AYRIK durumu değiştiği anda (tepki başlar, replik başlar/biter, yürüyen
varıp nesneyi göğse alır, eylem türü ya da plan değişir) beden eski pozdan yenisine TRANSITION_S süresinde sürekli geçer.
Durum değişiminin nedeni bilinmeden uygulanır: yeni bir durum eklenince geçiş kuralı ayrıca yazılmaz, yalnız durum imzasına girer.
Temas katmanları (atış kolu, el değiştirme, gösterme) bu geçişten SONRA uygulanır: kendi ağırlıklarıyla süreklidir ve temas anı kaymaz."""

TRANSITION_S = 0.25          # eski pozdan yenisine geçiş süresi (sn); en büyük kol hareketinde bile tek karede atlama sayılmayacak kadar uzun
SCAN_S = 1.0 / 48            # durum değişimi bu aralıkla aranır, sonra ikiye bölerek yeri bulunur (bundan kısa süren durum görülmez)
BEFORE_S = 1e-4              # değişimden hemen önceki an
MAX_CHAIN = 4                # üst üste binen geçişlerde geriye en çok bu kadar değişim izlenir

SCALARS = ("z", "sq", "lean", "yaw", "swL", "swR", "fL", "fR", "hL", "hR")     # konum (x) ve görünüş ('view', el biçimi) karışmaz
DEFAULTS = {"sq": 1.0}
ARM_K = 0.27                 # kol boyu / boy
FWD_SHORTEN = 0.28           # öne uzanan kol ekranda en çok bu oranda kısalır (çizimle aynı kural)
FWD_FULL = 1.3


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def arm_length(pose, side, height):
    """Pozda kolun ekrandaki boyu (m): yönlü uzanmada 'd', değilse öne uzanışa göre kısalan boy."""
    full = height * ARM_K
    if ("d" + side) in pose:
        return min(full, pose["d" + side])
    return full * (1.0 - FWD_SHORTEN * min(1.0, abs(pose["a" + side][0]) / FWD_FULL))


def blend(old, new, w, height):
    """new pozunun kopyası; beden ve kol alanları old -> new arasında w ağırlığıyla karışır (w=1: new)."""
    if w >= 1.0:
        return new
    mix = lambda a, b: a + (b - a) * w
    out = dict(new)
    for k in SCALARS:
        if k in old or k in new:
            out[k] = mix(float(old.get(k, DEFAULTS.get(k, 0.0))), float(new.get(k, DEFAULTS.get(k, 0.0))))
    for k in ("head", "aL", "aR"):
        out[k] = [mix(a, b) for a, b in zip(old[k], new[k])]
    for side in "LR":
        if ("d" + side) not in old and ("d" + side) not in new:
            continue
        out["d" + side] = mix(arm_length(old, side, height), arm_length(new, side, height))
        rw = lambda p: float(p.get("rw" + side, 1.0)) if ("d" + side) in p else 0.0
        out["rw" + side] = mix(rw(old), rw(new))
    return out


def last_change(state_at, t, window=TRANSITION_S):
    """(t - window, t] içinde durumun en son değiştiği an: (değişimden önceki an, yeni durumun ilk anı) ya da None.
    state_at(an) -> karşılaştırılabilir imza; None: o anda bu oyuncunun kesintisiz geçmişi yok (geçiş aranmaz)."""
    now = state_at(t)
    hi = t
    n = int(window / SCAN_S) + 1
    for i in range(1, n + 1):
        lo = max(t - window, t - i * SCAN_S)
        s = state_at(lo)
        if s is None:
            return None
        if s != now:
            while hi - lo > BEFORE_S:
                mid = (lo + hi) / 2.0
                if state_at(mid) == s:
                    lo = mid
                else:
                    hi = mid
            return lo, hi
        hi = lo
    return None


def apply(raw_at, state_at, t, height, depth=0):
    """t anının geçişli pozu. raw_at(an) -> o anın geçişsiz pozu; state_at(an) -> durum imzası."""
    pose = raw_at(t)
    change = None if depth >= MAX_CHAIN else last_change(state_at, t)
    if change is None:
        return pose
    before, start = change
    w = smooth((t - start) / TRANSITION_S)
    if w >= 1.0:
        return pose
    return blend(apply(raw_at, state_at, before, height, depth + 1), pose, w, height)
