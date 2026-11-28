"""AHOS bölüm süresi kapısı (V2): dizinin 'episode_defaults.min_seconds' değeri (proje verisi, motorda sabit yok)
altındaki bir planın TAM BÖLÜM olarak render edilmesi durur. Kısmi/deneme pencereleri (örn. ilk 12 sn) etkilenmez.

Ölçü: vuruş aralıklarının BİRLEŞİMİ (boşluk bırakıp 480'e uzatılmış plan sayılmaz). Tam bölüm sayılma: pencere 0'dan başlar
ve planın sonuna ulaşır. Bilerek kısa teslim için AHOS_ALLOW_SHORT=1 (taslak; kapı raporda 'allowed_short' yazar)."""


def _union_seconds(beats):
    iv = sorted((float(b.get("t_start", 0)), float(b.get("t_end", 0))) for b in beats if float(b.get("t_end", 0)) > float(b.get("t_start", 0)))
    total, cur_s, cur_e = 0.0, None, None
    for s, e in iv:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    return total + ((cur_e - cur_s) if cur_e is not None else 0.0)


def check(sheet, bible, t0, t1, env=None):
    """-> {"gated", "min_seconds", "planned_end", "covered_seconds", "full_window", "allowed_short", "problems": [str]}"""
    import os
    env = os.environ if env is None else env
    beats = (sheet or {}).get("beats") or []
    min_s = ((bible or {}).get("episode_defaults") or {}).get("min_seconds")
    covered = round(_union_seconds(beats), 2)
    end = round(max([float(b.get("t_end", 0)) for b in beats] or [0.0]), 2)
    full = float(t0) <= 0.0 and float(t1) >= end - 0.5 and end > 0
    rep = {"gated": bool(min_s), "min_seconds": min_s, "planned_end": end, "covered_seconds": covered,
           "full_window": full, "allowed_short": False, "problems": []}
    if not min_s or not full:
        return rep
    try:
        min_s = float(min_s)
    except (TypeError, ValueError):
        rep["problems"].append("episode_defaults.min_seconds sayı değil: %r" % (min_s,))
        return rep
    if covered + 1.0 < min_s:
        if str(env.get("AHOS_ALLOW_SHORT", "")).strip() == "1":
            rep["allowed_short"] = True
        else:
            rep["problems"].append("tam bölüm olarak render isteniyor ama planlanan vuruşlar %.1f sn kaplıyor (plan sonu %.1f sn); dizi en az %.0f sn istiyor"
                                   % (covered, end, min_s))
    return rep


def messages(rep):
    return list(rep.get("problems") or [])
