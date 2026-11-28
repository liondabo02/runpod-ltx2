"""AHOS kurgu listesi (diziden bağımsız, saf Python): bir vuruş hangi çekimlere bölünür ve her çekimin yavaş yaklaşması nereden nereye gider.

Kural: kesme ya GERÇEK bir kesmedir ya da yoktur. Kadrajı yalnız yüzde birkaç değiştiren 'kesme' seyirciye kameranın atlaması gibi görünür
(özellikle yürüyen oyuncu izlenirken). Bu yüzden:
- birbirine yakın kadrajlı ardışık planlar (genel/orta) tek çekimdir; yaklaşma çekim boyunca bir kez ilerler,
- MIN_CUT_S'den kısa son parça ayrı çekim olmaz,
- sürekli geçişte yeni vuruş aynı aile ve aynı kadroyla başlıyorsa çekim sürer (yaklaşma başa dönüp kadrajı geri sıçratmaz)."""
import math

import continuity

SUB_S = 3.5               # uzun vuruş bu aralıkla yeni çekim adayı üretir
LONG_BEAT_S = 5.0         # bundan kısa vuruş bölünmez
MIN_CUT_S = 1.0           # bundan kısa çekim kesilmez
ROTATION = ("wide", "medium", "close", "wide")
GROUP = ("wide", "medium")            # aralarındaki fark küçük (yaklaşık %10): aralarında kesme 'atlama' gibi okunur

# Gerçek kesme eşiği (tek kaynak: kamera ve atlama ölçüsü aynı değeri okur). 1280x720 ekran.
CUT_ZOOM_RATIO = 1.20                 # ölçek en az bu oranda değişir...
CUT_SHIFT_PX = (320, 180)             # ...ya da eski kadrajın merkezi yatayda/dikeyde en az bu kadar kayar
# İki FARKLI kadraj kuralı eşiği geçemeyecek kadar yakınsa kesme yoktur: kamera bir kadrajdan ötekine sürekli geçer.
JOIN_MARGIN = (1.03, 1.05)            # eşiğin kıl payı üstü de geçiş sayılır (karşılaştırılan iki kare arasında kadraj biraz kayar)
SOFT_MIN_S, SOFT_MAX_S = 0.4, 1.25    # geçiş süresi sınırları (sn)
SOFT_ZOOM_STEP = 0.022                # 12 fps karede en büyük ölçek adımı (ln); atlama ölçüsünün sınırının altında
SOFT_PAN_PX = 40.0                    # 12 fps karede en büyük kayma (px)


def is_real_cut(zoom_ratio, dx, dy, margin=(1.0, 1.0)):
    return (max(zoom_ratio, 1.0 / zoom_ratio) >= CUT_ZOOM_RATIO * margin[0]
            or abs(dx) >= CUT_SHIFT_PX[0] * margin[1] or abs(dy) >= CUT_SHIFT_PX[1] * margin[1])


def soft_seconds(zoom_ratio, dx, dy):
    """Yakın iki kadraj arasındaki sürekli geçişin süresi: yumuşatılmış eğrinin tepe hızı (ortalamanın 1,5 katı) kare başı sınırı aşmaz."""
    frames = 1.5 * max(abs(math.log(zoom_ratio)) / SOFT_ZOOM_STEP, max(abs(dx), abs(dy)) / SOFT_PAN_PX)
    return max(SOFT_MIN_S, min(SOFT_MAX_S, frames / 12.0))


def family(preset):
    return "group" if preset in GROUP else preset


def _candidates(beat):
    """[(başlangıç_sn, plan türü)] vuruş içi; birleştirmeden önceki aday çekimler."""
    dur = beat["t_end"] - beat["t_start"]
    first = beat.get("camera", "medium")
    if dur <= LONG_BEAT_S:
        return [(0.0, first)]
    out = [(0.0, first)]
    for sub in range(1, int(math.ceil(dur / SUB_S - 1e-9))):
        if dur - sub * SUB_S < MIN_CUT_S:
            break
        preset = ROTATION[(int(beat.get("i", 0)) + sub) % 4]
        if beat.get("props") and sub % 2 == 0:
            preset = "insert"
        out.append((sub * SUB_S, preset))
    return out


def _merged(beat):
    dur = beat["t_end"] - beat["t_start"]
    out = []
    for start, preset in _candidates(beat):
        if out and family(out[-1]["preset"]) == family(preset):
            continue                                            # aynı aile: kesme yok, önceki çekim sürer
        out.append({"start": start, "preset": preset})
    for a, b in zip(out, out[1:] + [{"start": dur}]):
        a["end"] = b["start"]
    return out


def continues(prev, beat):
    """beat, prev'in devamı mı: kesintisiz zaman, aynı mekân, sürekli geçiş, aynı kadro."""
    return (prev is not None and beat.get("transition_kind") not in continuity.FREE
            and abs(prev.get("t_end", -1.0) - beat.get("t_start", 0.0)) < 1e-6
            and prev.get("loc") == beat.get("loc") and set(prev.get("cast") or []) == set(beat.get("cast") or []))


def shots(beat):
    """Vuruşun çekimleri: [{'start','end','preset','push_from','push_to'}] (vuruş içi sn; push 0..1 yavaş yaklaşma oranı).
    beat['cut_in'] (link ile yazılır) doluysa ilk çekim önceki vuruşun son çekiminin devamıdır."""
    rows = [dict(s, push_from=0.0, push_to=1.0) for s in _merged(beat)]
    carry = beat.get("cut_in")
    if carry:
        rows[0].update(preset=carry["preset"], push_from=carry["push"], push_to=carry["push"])
    return rows


def link(prev, beat):
    """Planlayıcı, vuruşları SIRAYLA bağlar (üretim penceresi dışındakiler dahil): sonuç beat['cut_in'] olarak planın verisidir,
    parça parça üretimde de aynı kurgu çıkar. Dönüş: yazılan değer (devam yoksa None)."""
    beat["cut_in"] = None
    if continues(prev, beat):
        tail, first = shots(prev)[-1], _merged(beat)[0]
        if family(tail["preset"]) == family(first["preset"]) and (
                family(first["preset"]) == "group" or prev.get("focus") == beat.get("focus")):
            beat["cut_in"] = {"preset": tail["preset"], "push": tail["push_to"]}
    return beat["cut_in"]


def window_context(rows):
    """rows: [(vuruş, pencerede_mi)] sırayla. Pencerenin iki ucundan kesintisiz süren (pencere dışı) komşu vuruşlar: çizilmez, yalnız çekim kararında okunur."""
    inside = [i for i, (_b, w) in enumerate(rows) if w]
    out = []
    for edge, step in ((inside[0], -1), (inside[-1], 1)) if inside else ():
        i = edge
        while 0 <= i + step < len(rows) and not rows[i + step][1]:
            a, b = sorted((i, i + step))
            if not continues(rows[a][0], rows[b][0]):
                break
            i += step
            out.append(rows[i][0])
    return out


def at(beat, lt):
    """lt anındaki çekim: (plan türü, yaklaşma oranı, çekim sırası)."""
    rows = shots(beat)
    k = max(i for i, s in enumerate(rows) if s["start"] <= lt + 1e-9)
    s = rows[k]
    u = max(0.0, min(1.0, (lt - s["start"]) / max(s["end"] - s["start"], 0.1)))
    return s["preset"], s["push_from"] + (s["push_to"] - s["push_from"]) * u, k


# ---------------------------------------------------------------- son plan seçimi: anlık plan kırıntısı eritilir
CRUMB_EPS = 1e-3


def _fits(target, piece):
    """target planı piece'in süresini üstlenebilir mi? Sabit kadraj (bounds dolu) yalnız kendi vuruşunun içinde uzayabilir."""
    b = target["bounds"]
    return b is None or (piece["a"] >= b[0] - 1e-6 and piece["b"] <= b[1] + 1e-6)


def _join_equal(segs):
    out = []
    for s in segs:
        if s["b"] - s["a"] <= 1e-9:
            continue
        if out and out[-1]["key"] == s["key"]:
            out[-1] = dict(out[-1], b=s["b"], parts=out[-1]["parts"] + s["parts"])
        else:
            out.append(s)
    return out


def dissolve_crumbs(segs, min_s):
    """Bütün kamera katmanlarının BİRLEŞİMİNDEN çıkan kesintisiz plan dizisinde min_s'den kısa plan bırakmaz.
    segs: [{'key', 'a', 'b', 'bounds': None | (a, b), 'parts': [kaynak aralıkları]}] (mutlak sn, bitişik, sıralı).
    En kısa kırıntıdan başlanır: iki yanı aynı plansa üçü tek plan olur; değilse ÖNCEKİ plan uzar (sıradaki kesme zamanında kalır),
    olamıyorsa sonraki plan erken başlar. Sabit kadraj (bounds dolu) kısaysa kendisi kısaltılmaz: yanındaki serbest plandan süre alır.
    Hiçbir yere eritilemeyen kırıntı olduğu gibi kalır (ölçü ve render kapısı bildirir)."""
    segs = _join_equal([dict(s, parts=list(s["parts"])) for s in segs])
    stuck = set()
    for _ in range(4 * len(segs) + 4):
        short = [(s["b"] - s["a"], i) for i, s in enumerate(segs)
                 if s["b"] - s["a"] < min_s - CRUMB_EPS and (s["a"], s["b"]) not in stuck]
        if len(segs) < 2 or not short:
            break
        i = min(short)[1]
        x = segs[i]
        prev, nxt = segs[i - 1] if i else None, segs[i + 1] if i + 1 < len(segs) else None
        if x["bounds"] is not None:
            before = x["b"] - x["a"]
            if nxt is not None and nxt["bounds"] is None:
                end = max(x["b"], min(x["a"] + min_s, x["bounds"][1], nxt["b"]))
                x["b"] = nxt["a"] = end
            if x["b"] - x["a"] < min_s - CRUMB_EPS and prev is not None and prev["bounds"] is None:
                start = min(x["a"], max(x["b"] - min_s, x["bounds"][0], prev["a"]))
                x["a"] = prev["b"] = start
            if x["b"] - x["a"] > before + 1e-9:
                segs = _join_equal(segs)
                continue
        if prev is not None and _fits(prev, x):
            prev["b"] = x["b"]
        elif nxt is not None and _fits(nxt, x):
            nxt["a"] = x["a"]
        else:
            stuck.add((x["a"], x["b"]))
            continue
        del segs[i]
        segs = _join_equal(segs)
    return segs
