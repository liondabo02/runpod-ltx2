"""Yerleşim çözücü (genel motor): koreografideki temas olaylarının (el değiştirme, atış/bırakma) fiziksel olarak OKUNABİLİR olması için
karakter konumlarını (yalnız planlayıcının kendi kopyasında) düzeltir ve yaptığı her değişikliği raporlar. Hiçbir filme/sahneye özel değildir.
Kurallar: (1) el değiştiren iki kişi arası mesafe = ortak kol erişiminin ~0.85'i (çocuk-yetişkin boyuna göre); (2) atışta atan ile hedef arası 0.7–2.0 m;
(3) çözemezse (ör. iki kişi aynı anda iki yere gerekli) not düşer, gizlemez."""
import object_state

ARM = 0.27
SEP_K = 0.85                   # el değiştirmede hedef mesafe / ortak erişim
THROW_MIN, THROW_MAX, THROW_IDEAL = 0.7, 2.0, 1.0


def _xat(mot, cid, frac=0.0):
    m = mot.get(cid) or {}
    return float(m.get("x0", 0.0)) + (float(m.get("x1", m.get("x0", 0.0))) - float(m.get("x0", 0.0))) * frac


def _set_x(mot, cid, x):
    mot[cid]["x0"] = mot[cid]["x1"] = round(x, 3)


def resolve(motion, objects, heights, targets, beat_len=8.0):
    """motion: {cid: {kind,x0,x1,...}} (yerinde değiştirilir). Dönüş: notlar listesi [{'rule','actor','from','to','why'}]."""
    notes = []; locked = set()
    for ob in objects or []:
        tr = ob.get("track") or []
        for e in object_state.events(tr):
            if e["type"] == "handoff" and e["by"] in motion and e["to"] in motion and e["by"] in heights and e["to"] in heights:
                reach = ARM * (heights[e["by"]] + heights[e["to"]]); want = SEP_K * reach
                xg, xr = _xat(motion, e["by"]), _xat(motion, e["to"])
                sep = abs(xr - xg)
                if not (0.7 * want <= sep <= 1.2 * want):
                    mover = e["to"] if e["to"] not in locked else e["by"]
                    anchor = e["by"] if mover == e["to"] else e["to"]
                    sgn = 1.0 if _xat(motion, mover) >= _xat(motion, anchor) else -1.0
                    new = _xat(motion, anchor) + sgn * want
                    notes.append({"rule": "handoff_separation", "actor": mover, "from": round(_xat(motion, mover), 2), "to": round(new, 2),
                                  "why": f"mesafe {sep:.2f} m, ortak erişim {reach:.2f} m; hedef {want:.2f} m"})
                    _set_x(motion, mover, new); locked.update((anchor, mover))
            if e["type"] in ("dispose", "drop") and e["by"] in motion:
                for k in tr:
                    if isinstance(k.get("at"), str) and k["at"] in targets and k["t"] == e["t"]:
                        tx = targets[k["at"]][0]; hx = _xat(motion, e["by"]); dx = abs(tx - hx)
                        if e["by"] in locked:
                            notes.append({"rule": "throw_distance", "actor": e["by"], "from": round(hx, 2), "to": round(hx, 2), "why": f"çözülemedi: aynı vuruşta el değiştirme konumu kilitli (atış mesafesi {dx:.2f} m)"}); continue
                        if not (THROW_MIN <= dx <= THROW_MAX):
                            sgn = -1.0 if hx <= tx else 1.0
                            clash = lambda xx: any(abs(v[0] - xx) < 0.6 for n_, v in targets.items() if n_ != k["at"])   # başka hedefin (kutu) önüne durma
                            if clash(tx + sgn * THROW_IDEAL) and not clash(tx - sgn * THROW_IDEAL):
                                sgn = -sgn
                            new = tx + sgn * THROW_IDEAL
                            notes.append({"rule": "throw_distance", "actor": e["by"], "from": round(hx, 2), "to": round(new, 2), "why": f"atış mesafesi {dx:.2f} m, aralık {THROW_MIN}-{THROW_MAX} m"})
                            _set_x(motion, e["by"], new)
    return notes
