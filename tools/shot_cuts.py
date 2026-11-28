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
