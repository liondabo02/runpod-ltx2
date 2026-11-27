"""Yerleşim çözücü (genel motor). Temas olaylarının (el değiştirme, atış/bırakma) fiziksel olarak mümkün ve okunabilir olması için karakter konumlarını
YALNIZ planlayıcının kendi kopyasında düzeltir ve her kararı raporlar. Hiçbir filme/sahneye özel değildir.

Kısıt türleri (ayrı tutulur):
  CONSTRAINT  fiziksel/geometrik: kol erişimi (iki kişinin ortak kolu), beden çakışması, zemin. İhlal edilirse düzeltme ZORUNLU.
  PREFERENCE  yönetmenlik/okunabilirlik: atış mesafesi (karakter ölçeği, nesne ağırlığı, atış türü, hedefe göre hesaplanır), tercih edilen uzaklık.
              Yalnız tercih bandı dışındaysa ve fiziksel kısıtı bozmuyorsa ayarlanır.
  INTENT      senaryonun istediği konum/aksiyon: korunur. Çözücü hikâyeyi (kim kime verir, nereye atar) ASLA değiştirmez.
Konum değişimi ışınlanma olarak yapılmaz: karakter önceki planın bittiği yerden (prev_x) o konuma YÜRÜR ve temastan önce varır (walk_s).
Çözülemezse çelişen kısıtlar 'conflict' notu olarak bildirilir; sessizce yutulmaz."""
import object_state
import shot_motion as sm

ARM = 0.27
CLEARANCE_K = 0.40        # beden çakışmaması: el değiştirmede mesafe >= 0.40 * ortak erişim (CONSTRAINT)
REACH_K = 0.95            # eller buluşsun: mesafe <= 0.95 * ortak erişim (CONSTRAINT)
PREF_K = 0.85             # tercih edilen mesafe / ortak erişim (PREFERENCE)
VMAX = 1.5                # m/sn, yetişkin yürüyüş üst sınırı (boya göre ölçeklenir)
LEAD = 0.4                 # temas hazırlığından önce varış payı (sn)
RATIO_MAX = 0.999        # el değiştirme erişim oranı üst sınırı (çizim kontrolü >1.0'ı reddeder)                


def _x0(m): return float(m.get("x0", 0.0))
def _x1(m): return float(m.get("x1", m.get("x0", 0.0)))


def throw_range(h_holder, weight=0.5, kind="toss"):
    """Atış için okunur mesafe aralığı: atanın boyuna, nesnenin ağırlığına ve atış türüne bağlı (sabit aralık yok)."""
    lo = max(0.45, 0.45 * h_holder)
    reach = 1.6 if kind == "toss" else 2.4                       # toss: alttan yumuşak; lob: yüksek yay
    hi = max(lo + 0.3, reach * h_holder / (0.6 + weight))
    return lo, hi


def _walk_to(motion, cid, new_x, heights, t_event, prev_x, notes, why, rule):
    m = motion[cid]; start = prev_x.get(cid, _x0(m)); dist = abs(new_x - start)
    vmax = VMAX * max(0.5, heights.get(cid, 1.7) / 1.7)
    avail = max(0.0, t_event - LEAD)
    if dist > 1e-3 and avail * vmax < dist:
        notes.append({"rule": rule, "kind": "conflict", "actor": cid, "why": f"çelişki: {why}; ancak {cid} {dist:.2f} m yürümeli, hazırlık süresi {avail:.2f} sn (üst hız {vmax:.1f} m/sn) yetmiyor — önceki planda yerleşmeli ya da temas geç başlamalı"})
        return False
    m["x0"] = round(start, 3); m["x1"] = round(new_x, 3)
    if dist > 1e-3:
        m["kind"] = "walk"; m["walk_s"] = round(max(0.9, avail / 0.85), 2)           # te = 0.85*walk_s: temastan önce varır
    notes.append({"rule": rule, "kind": "adjusted", "actor": cid, "from": round(start, 2), "to": round(new_x, 2), "why": why})
    return True


def resolve(motion, objects, heights, targets, prev_x=None, weights=None, reach_fn=None, dur=None):
    """reach_fn(by, xg, to, xr) -> erişim oranı (<=1 kollar buluşur): verilirse el değiştirme kısıtı ÇİZİMİN kullandığı aynı ölçüyle (omuz yüksekliği farkı dahil)
    değerlendirilir; yoksa yalnız yatay aralık kuralı geçerlidir. motion yerinde değiştirilir. prev_x: {karakter: önceki planın bitiş x'i} (süreklilik). Dönüş: notlar listesi [{'rule','kind','actor',...}]."""
    notes = []; prev_x = prev_x or {}; weights = weights or {}; locked = set()
    for ob in objects or []:
        tr = ob.get("track") or []
        for e in object_state.events(tr):
            if e["type"] == "handoff" and e["by"] in motion and e["to"] in motion and e["by"] in heights and e["to"] in heights:
                reach = ARM * (heights[e["by"]] + heights[e["to"]])
                xg, xr = _x1(motion[e["by"]]), _x1(motion[e["to"]]); sep = abs(xr - xg)
                lo, hi, want = CLEARANCE_K * reach, REACH_K * reach, PREF_K * reach
                if reach_fn is not None:
                    def _at(c_, m_=None):                        # temas anında ÇİZİLEN konum (boşta sallanma dahil); süre bilinmiyorsa işaret konumu
                        m_ = m_ or motion[c_]
                        return sm.motion_x(m_, e["t"], dur, heights[c_]) if dur else _x1(m_)
                    xg, xr = _at(e["by"]), _at(e["to"])
                    r0 = reach_fn(e["by"], xg, e["to"], xr)
                    if r0 <= RATIO_MAX:
                        notes.append({"rule": "handoff_separation", "kind": "ok", "actor": e["to"], "why": f"erişim oranı {r0:.2f} (<=1), mesafe {abs(xr - xg):.2f} m"})
                        locked.update((e["by"], e["to"])); continue
                    mover = e["to"] if e["to"] not in locked else e["by"]; anchor = e["by"] if mover == e["to"] else e["to"]
                    ax_ = _at(anchor); sgn = 1.0 if _x1(motion[mover]) >= _x1(motion[anchor]) else -1.0
                    ratio = lambda m_x: reach_fn(e["by"], m_x if mover == e["by"] else ax_, e["to"], m_x if mover == e["to"] else ax_)
                    cands = [round(0.05 * k, 2) for k in range(1, 40)]
                    feas = [c for c in cands if ratio(ax_ + sgn * c) <= RATIO_MAX]
                    if mover in locked or not feas:
                        why = "kollar hiçbir yatay aralıkta buluşamıyor (omuz yüksekliği farkı; eğilme/çömelme yeteneği gerekir)" if not feas else "çelişki: konum başka bir temas için kilitli"
                        notes.append({"rule": "handoff_separation", "kind": "conflict", "actor": mover, "why": f"erişim oranı {r0:.2f} > 1: {why}"})
                    else:
                        best = min(feas, key=lambda c: (abs(c - abs(xr - xg)), ratio(ax_ + sgn * c)))
                        _walk_to(motion, mover, ax_ + sgn * best, heights, e["t_start"], prev_x, notes, f"erişim oranı {r0:.2f} > 1 (mesafe {abs(xr - xg):.2f} m)", "handoff_separation")
                    locked.update((anchor, mover)); continue
                if lo <= sep <= hi:
                    notes.append({"rule": "handoff_separation", "kind": "ok", "actor": e["to"], "why": f"mesafe {sep:.2f} m fiziksel aralıkta [{lo:.2f}, {hi:.2f}]"})
                    locked.update((e["by"], e["to"])); continue
                mover = e["to"] if e["to"] not in locked else e["by"]; anchor = e["by"] if mover == e["to"] else e["to"]
                sgn = 1.0 if _x1(motion[mover]) >= _x1(motion[anchor]) else -1.0
                new = _x1(motion[anchor]) + sgn * want
                if mover in locked or not _walk_to(motion, mover, new, heights, e["t_start"], prev_x, notes,
                                                   f"mesafe {sep:.2f} m, fiziksel aralık [{lo:.2f}, {hi:.2f}] (ortak erişim {reach:.2f} m)", "handoff_separation"):
                    if mover in locked:
                        notes.append({"rule": "handoff_separation", "kind": "conflict", "actor": mover, "why": "çelişki: konum başka bir temas için kilitli"})
                locked.update((anchor, mover))
            if e["type"] in ("dispose", "drop") and e["by"] in motion and e["by"] in heights:
                for k in tr:
                    if isinstance(k.get("at"), str) and k["at"] in targets and k["t"] == e["t"]:
                        tx = targets[k["at"]][0]; hx = _x1(motion[e["by"]]); dx = abs(tx - hx)
                        lo, hi = throw_range(heights[e["by"]], weights.get(ob.get("prop"), object_state.weight_of(ob.get("prop", ""))), k.get("throw", "toss"))
                        if lo <= dx <= hi:
                            notes.append({"rule": "throw_distance", "kind": "ok", "actor": e["by"], "why": f"atış mesafesi {dx:.2f} m aralıkta [{lo:.2f}, {hi:.2f}]"}); continue
                        if e["by"] in locked:
                            notes.append({"rule": "throw_distance", "kind": "conflict", "actor": e["by"], "why": f"çelişki: atış mesafesi {dx:.2f} m [{lo:.2f}, {hi:.2f}] dışında; ama aynı planda el değiştirme konumu kilitli (fiziksel kısıt) — tercih feda edilir, kamera/plan bölünmeli"}); continue
                        sgn = -1.0 if hx <= tx else 1.0; ideal = min(max(1.0 * heights[e["by"]] / 1.7 + 0.2, lo), hi)
                        clash = lambda xx: any(abs(v[0] - xx) < 0.6 for n_, v in targets.items() if n_ != k["at"])    # başka kutunun önüne durma
                        if clash(tx + sgn * ideal) and not clash(tx - sgn * ideal):
                            sgn = -sgn
                        _walk_to(motion, e["by"], tx + sgn * ideal, heights, e["t_start"] - 0.5, prev_x, notes, f"atış mesafesi {dx:.2f} m, okunur aralık [{lo:.2f}, {hi:.2f}] (boy {heights[e['by']]:.2f} m)", "throw_distance")
    return notes
