"""AHOS eylem izlenebilirliği (diziden ve dilden bağımsız, saf Python): metnin/storyboard'un istediği eylem üretim verisinde var mı?

Motor eylem METNİNİ yorumlamaz; içinde hiçbir dilin sözcüğü yoktur. İstek iki yoldan veriyle gelir:
  1) vuruş alanı  "required_actions": [{"do": tür, "by": oyuncu, "to": hedef (isteğe bağlı)}]      (storyboard katmanı)
  2) dizi verisi  series/<id>/action_cues.json = {"point": ["..."], "give": ["..."]}               (dizinin kendi dilinde ipucu sözleri)
     İpucu sözü eylem metninde sözcük başından aranır ("göster" -> "gösterir"). Eşleşen vuruşta o türden veri yoksa vuruş geçmez;
     bilerek istenmiyorsa gerekçe yazılır: "action_waivers": {tür: "neden"}.
Türler ve karşılıkları: point = choreo.points; take = nesne yerden ele; give = nesne elden ele; release = nesne elden yere/hedefe;
move = choreo.motion'da yer değiştiren hareket.
Ne istek ne ipucu olan eylem metinli vuruş DENETLENMEMİŞTİR ve raporda 'untraced_beats' olarak açıkça yazılır (geçti sayılmaz).
Sınır: ipucu sözü eylemi KİMİN yaptığını söylemez (o türden herhangi bir veri yeter); kişi/hedef eşleşmesi yalnız required_actions ile denetlenir."""
import json
import os
import re

import continuity
import object_state

KINDS = ("point", "take", "give", "release", "move")
CUE_FILE = "action_cues.json"
_EVENT_KIND = {"pickup": "take", "handoff": "give", "drop": "release", "dispose": "release"}


def load_cues(series_dir):
    """(ipuçları ya da None, sorunlar). Dosya yoksa ipucu yoktur; bozuk dosya sessizce yok sayılmaz."""
    path = os.path.join(series_dir, CUE_FILE)
    if not os.path.exists(path):
        return None, []
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return None, [_p("IPUCU_SOZLUGU_GECERSIZ", None, f"{CUE_FILE} okunamıyor: {e}")]
    bad = []
    if not isinstance(raw, dict) or not raw:
        bad.append("kök boş olmayan bir sözlük olmalı")
    else:
        for k, v in raw.items():
            if k not in KINDS:
                bad.append(f"bilinmeyen eylem türü '{k}' (türler: {', '.join(KINDS)})")
            elif not (isinstance(v, list) and v and all(isinstance(s, str) and len(s.strip()) >= 2 for s in v)):
                bad.append(f"'{k}' en az 2 harfli sözlerden oluşan dolu bir liste olmalı")
    if bad:
        return None, [_p("IPUCU_SOZLUGU_GECERSIZ", None, f"{CUE_FILE}: {b}") for b in bad]
    return raw, []


def _p(rule, beat, why):
    return {"rule": rule, "beat": beat, "why": why}


def _fold(text):
    return " ".join(str(text or "").replace("İ", "i").casefold().split())


def cue_hits(text, cues):
    """{tür: eşleşen ilk söz}; söz yalnız sözcük başından eşleşir."""
    t, out = _fold(text), {}
    for kind, words in (cues or {}).items():
        for w in words:
            if re.search(r"(?<!\w)" + re.escape(_fold(w)), t):
                out[kind] = w
                break
    return out


def implemented(beat):
    """Vuruşun üretim verisinde gerçekten bulunan eylemler: [{"do", "by", "to"}] (yalnız choreo; metinden çıkarım yok)."""
    ch = beat.get("choreo") or {}
    out = [{"do": "point", "by": it.get("by"), "to": it.get("to")} for it in ch.get("points") or []]
    for ob in ch.get("objects") or []:
        for e in object_state.events(ob.get("track") or []):
            kind = _EVENT_KIND[e["type"]]
            if kind == "take":
                to = {"prop": ob.get("prop")}
            elif kind == "give":
                to = e["to"]
            else:                                                   # bırakılan yer: iz anahtarındaki hedef
                to = next((k.get("at") for k in ob["track"] if k.get("t") == e["t"] and "at" in k), None)
            out.append({"do": kind, "by": e["by"], "to": to, "prop": ob.get("prop")})
    out += [{"do": "move", "by": c, "to": None} for c, m in (ch.get("motion") or {}).items()
            if m.get("kind") in continuity.MOVING and float(m.get("x1", m.get("x0", 0.0))) != float(m.get("x0", 0.0))]
    return out


def _matches(want, have):
    if have["do"] != want["do"] or have["by"] != want["by"]:
        return False
    to = want.get("to")
    if to is None:
        return True
    if isinstance(to, dict):                                        # {"prop": ad}: gösterilen/alınan/verilen nesne
        return (isinstance(have["to"], dict) and have["to"].get("prop") == to.get("prop")) or have.get("prop") == to.get("prop")
    return have["to"] == to


def check_beat(beat, index, cues=None):
    """(sorunlar, satır). Satır: istenen/bulunan eylemler, kullanılan muafiyetler, vuruş izlenebiliyor mu."""
    probs, name = [], beat.get("shot_id") or index
    have = implemented(beat)
    waivers = beat.get("action_waivers") or {}
    if not isinstance(waivers, dict) or any(k not in KINDS or not str(v or "").strip() for k, v in waivers.items()):
        probs.append(_p("EYLEM_ALANI_GECERSIZ", name, "action_waivers: {bilinen tür: boş olmayan gerekçe} olmalı"))
        waivers = {}
    wanted = beat.get("required_actions")
    if wanted is not None and not isinstance(wanted, list):
        probs.append(_p("EYLEM_ALANI_GECERSIZ", name, "required_actions bir liste olmalı"))
        wanted = []
    cast = beat.get("characters") or []
    for w in wanted or []:
        if not isinstance(w, dict) or w.get("do") not in KINDS or not w.get("by") or (cast and w["by"] not in cast):
            probs.append(_p("EYLEM_ALANI_GECERSIZ", name, f"geçersiz istek {w!r}: 'do' bilinen tür, 'by' vuruş kadrosunda olmalı"))
        elif not any(_matches(w, h) for h in have):
            to = "" if w.get("to") is None else f" -> {w['to']}"
            probs.append(_p("EYLEM_UYGULANMAMIS", name, f"istenen eylem üretim verisinde yok: {w['do']} ({w['by']}{to})"))
    hits = cue_hits(beat.get("action"), cues)
    waived = {}
    for kind, word in sorted(hits.items()):
        if any(h["do"] == kind for h in have):
            continue
        if kind in waivers:
            waived[kind] = str(waivers[kind])
        elif not any(isinstance(w, dict) and w.get("do") == kind for w in wanted or []):     # istek zaten ayrıca raporlandı
            probs.append(_p("METIN_EYLEMI_IZSIZ", name, f"eylem metni '{word}' diyor ({kind}) ama vuruşta bu türden veri yok; "
                                                        f"veriyi ekleyin ya da action_waivers.{kind} gerekçesi yazın"))
    row = {"beat": name, "cues": hits, "required": len(wanted or []), "waived": waived,
           "traced": bool(hits or wanted) or not str(beat.get("action") or "").strip()}
    return probs, row


def check(sheet, series_dir, t0=0.0, t1=float("inf")):
    """Pencereye giren vuruşlar için rapor: {'problems', 'beats', 'untraced_beats', 'cue_file'}."""
    cues, probs = load_cues(series_dir)
    rows = []
    for i, b in enumerate(sheet.get("beats", [])):
        if float(b.get("t_end", 0)) <= t0 or float(b.get("t_start", 0)) >= t1:
            continue
        pr, row = check_beat(b, i, cues)
        probs += pr
        rows.append(row)
    return {"problems": probs, "beats": rows, "untraced_beats": [r["beat"] for r in rows if not r["traced"]], "cue_file": cues is not None}


def messages(report):
    return [f"[script] {p['rule']} {p['beat'] if p['beat'] is not None else '-'}: {p['why']}" for p in report["problems"]]
