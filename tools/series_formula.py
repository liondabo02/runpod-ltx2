#!/usr/bin/env python3
"""Dizi formülü motoru: bir dizi TÜRÜNÜN (format) yapısını veriden okur, bölüm iskeleti çıkarır ve denetler.

Formatlar: studio/formats/<id>.json (örn. gizem_komedi_ekibi, sessiz_kovalamaca, koy_toplulugu).
Bir format yalnız tür ve yapıyı tanımlar; karakter/isim/görünüş özgündür (yasak_isimler denetlenir).

Kullanan işçiler:
  - Yönetmen (showrunner): yeni dizide `detect` + `director_block` -> karakterlere formula_role yazdırır;
    `cast_errors` bible'ı denetler.
  - Senaryo Odası (writers_room): `writer_block` -> bölüm iskeleti ve slot sözlüğü; her vuruşa formula_slot yazar.
  - Senaryo Denetçisi: `episode_errors` -> yapı, süre payı, kurallar (ipucu önce, diyalog oranı, şaka yoğunluğu...).
  - Yazılım Şirketi: `readiness` -> formülün istediği motor yeteneklerinin kanıttan hesaplanan durumu.

Komut satırı:
  python tools/series_formula.py liste
  python tools/series_formula.py iskelet <format_id> [--sure 480]
  python tools/series_formula.py denetle <format_id> <beat_sheet.json> [--bible series-bible.json]
  python tools/series_formula.py hazirlik [<format_id>]
Yalnız standart kütüphane; ağ yok, model çağrısı yok.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FORMAT_DIR = os.path.join("studio", "formats")
_TR = str.maketrans("çğıöşüâîûÇĞİÖŞÜ", "cgiosuaiuCGIOSU")


def _fold(t):
    return str(t or "").translate(_TR).lower()


def _lower_tr(t):
    """Türkçe harfleri KORUYARAK küçült (öldü != oldu); yalnız I/İ doğru eşlenir."""
    return str(t or "").replace("I", "ı").replace("İ", "i").lower()


def format_ids(root=ROOT):
    d = os.path.join(root, FORMAT_DIR)
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def load(fid, root=ROOT):
    if not re.fullmatch(r"[a-z0-9_]{1,40}", str(fid or "")):
        raise ValueError("geçersiz format kimliği: %r" % fid)
    with open(os.path.join(root, FORMAT_DIR, fid + ".json"), encoding="utf-8") as f:
        return json.load(f)


def of_bible(bible, root=ROOT):
    fid = (bible or {}).get("format_id")
    return load(fid, root) if fid else None


def detect(command, root=ROOT):
    """Komuttan format seçer: açık 'format: <id>' ya da anahtar kelime sayısı en yüksek format (en az 1). Yoksa None."""
    text = _fold(command)
    m = re.search(r"format\s*[:=]\s*([a-z0-9_]+)", text)
    ids = format_ids(root)
    if m and m.group(1) in ids:
        return m.group(1)
    best, score = None, 0
    for fid in ids:
        n = sum(1 for k in load(fid, root).get("anahtar_kelimeler", []) if re.search(r"\b%s" % re.escape(_fold(k)), text))
        if n > score:
            best, score = fid, n
    return best


def _slots(fmt):
    return {s["slot"]: s for s in fmt["yapi"]}


def skeleton(fmt, seconds):
    """Sıralı (serbest olmayan) slotlara pay ortasına göre zaman penceresi verir. Döner: [{slot, ad, t0, t1, tanim}]."""
    seq = [s for s in fmt["yapi"] if not s.get("serbest") and s.get("pay") and s.get("zorunlu", True)]
    w = [sum(s["pay"]) / 2.0 for s in seq]
    tot = sum(w) or 1.0
    out, t = [], 0.0
    for s, x in zip(seq, w):
        d = seconds * x / tot
        out.append({"slot": s["slot"], "ad": s["ad"], "t0": round(t, 1), "t1": round(t + d, 1), "tanim": s["tanim"]})
        t += d
    if out:
        out[-1]["t1"] = float(seconds)
    return out


def _rule_text(r):
    k = r["tur"]
    if k == "once":
        s = "maske/çözüm '%s' gelmeden en az %d '%s' vuruşu" % (r["once_slot"], r["en_az"], r["slot"])
    elif k == "slot_rol":
        s = "'%s' vuruşunda '%s' rolünden bir karakter" % (r["slot"], r["rol"])
    elif k == "slot_karakter":
        s = "'%s' vuruşlarında en az %d farklı karakter%s" % (r["slot"], r["en_az"], (" ('%s' rolünden)" % r["rol"]) if r.get("rol") else "")
    elif k == "diyalog_orani":
        s = "diyaloglu vuruş oranı %%%d-%%%d" % (r["min"] * 100, r["max"] * 100)
    elif k == "dakikada":
        s = "dakikada en az %.1f '%s' vuruşu" % (r["en_az"], r["slot"])
    elif k == "alan_dolu":
        s = "her '%s' vuruşunda '%s' alanı dolu" % (r["slot"], r["alan"])
    elif k == "motif_tekrar":
        s = "bir şaka motifi ('%s' alanı) en az %d kez, her seferinde büyüyerek" % (r["alan"], r["en_az"])
    elif k == "yasak_kelime":
        s = "şiddet/kalıcı zarar kelimesi yok"
    else:
        s = k
    return s + ((" — " + r["neden"]) if r.get("neden") else "")


def director_block(fmt):
    roles = "; ".join("%s (%s, %d-%d kişi): %s" % (r["id"], r["ad"], r["min"], r["max"], r["tanim"]) for r in fmt["roller"])
    extra = ""
    for c in fmt.get("oyuncu_kurallari", []):
        if c["tur"] == "benzersiz_alan":
            extra += " '%s' rolündeki her karaktere farklı bir '%s' alanı yaz." % (c["rol"], c["alan"])
    return ("DİZİ FORMÜLÜ: %s. Ton: %s. Her karaktere bu rollerden birini 'formula_role' alanıyla ver: %s.%s "
            "Tür ve yapı esinlenmedir; karakter, isim, tür ve görünüş TAMAMEN ÖZGÜN olsun, bilinen bir çizgi filmden isim ya da "
            "karakter kullanma (yasak: %s). Bölümlerde her karakterin rolüne uygun davranacağını düşünerek kişilik yaz."
            % (fmt["ad"], fmt["ton"], roles, extra, ", ".join(fmt.get("yasak_isimler", [])[:12])))


def writer_block(fmt, seconds, t0=None, t1=None):
    """Senaryo odası yönergesi. t0/t1 verilirse o perdenin penceresine düşen slotlar öne çıkarılır."""
    sk = skeleton(fmt, seconds)
    lines = ["DİZİ FORMÜLÜ (%s): ton %s." % (fmt["ad"], fmt["ton"]),
             "Her vuruşa 'formula_slot' alanı yaz; değeri şu sözlükten: " +
             ", ".join("%s (%s)" % (s["slot"], s["ad"]) for s in fmt["yapi"]) + "."]
    win = [s for s in sk if t0 is None or (s["t1"] > t0 and s["t0"] < t1)]
    lines.append(("Bu perdenin (%s-%s sn) iskeleti: " % (t0, t1) if t0 is not None else "Bölüm iskeleti: ") +
                 " -> ".join("%s %s-%s sn: %s" % (s["slot"], s["t0"], s["t1"], s["tanim"]) for s in win))
    free = [s for s in fmt["yapi"] if s.get("serbest")]
    if free:
        lines.append("İskelete serpiştirilecek vuruşlar: " + "; ".join(
            "%s %d-%d adet: %s" % (s["slot"], s["adet"][0], s["adet"][1], s["tanim"]) for s in free))
    lines.append("Kurallar: " + "; ".join(_rule_text(r) for r in fmt.get("kurallar", [])) + ".")
    if any(r["tur"] == "motif_tekrar" for r in fmt.get("kurallar", [])):
        lines.append("Şaka vuruşlarına 'gag_motif' alanı yaz (tekrar eden motifin kısa adı).")
    return " ".join(lines)


def _name_hits(name, banned):
    n = _fold(name)
    return [b for b in banned if re.search(r"(^|[^a-z0-9])%s($|[^a-z0-9])" % re.escape(_fold(b)), n)]


def cast_errors(bible, fmt=None, root=ROOT):
    """Bible'ın formülün rol tablosuna uyması ve isim özgünlüğü. Format yoksa boş liste."""
    fmt = fmt or of_bible(bible, root)
    if not fmt:
        return []
    errs, chars = [], bible.get("characters", []) or []
    roles = {r["id"]: r for r in fmt["roller"]}
    count = {k: 0 for k in roles}
    for c in chars:
        r = c.get("formula_role")
        if r not in roles:
            errs.append("FORMUL_ROLU_YOK: %s için formula_role %r (olası: %s)" % (c.get("id"), r, ", ".join(roles)))
        else:
            count[r] += 1
        for field in ("name", "id"):
            hits = _name_hits(c.get(field, ""), fmt.get("yasak_isimler", []))
            if hits:
                errs.append("OZGUN_DEGIL: %s adı bilinen esere ait (%s)" % (c.get("id"), ", ".join(hits)))
                break
    for k, r in roles.items():
        if not (r["min"] <= count[k] <= r["max"]):
            errs.append("ROL_SAYISI: %s rolünde %d karakter var, %d-%d olmalı" % (k, count[k], r["min"], r["max"]))
    for c in fmt.get("oyuncu_kurallari", []):
        if c["tur"] == "benzersiz_alan":
            vals = [_fold(x.get(c["alan"], "")).strip() for x in chars if x.get("formula_role") == c["rol"]]
            if any(not v for v in vals):
                errs.append("ALAN_EKSIK: %s rolündeki her karakterde '%s' dolu olmalı" % (c["rol"], c["alan"]))
            if len([v for v in vals if v]) != len({v for v in vals if v}):
                errs.append("ALAN_TEKRARI: %s rolünde '%s' değerleri farklı olmalı" % (c["rol"], c["alan"]))
    return errs


def _dur(b):
    try:
        return max(0.0, float(b.get("t_end", 0)) - float(b.get("t_start", 0)))
    except (TypeError, ValueError):
        return 0.0


def _has_dialogue(b):
    return bool(str(b.get("dialogue") or "").strip())


def episode_errors(beats, fmt, bible=None, seconds=None):
    """Bölümün formüle uyumu. Döner: sorun listesi (boş = uyumlu). Yaratıcı kalite DEĞİL, yapı denetimidir."""
    errs = []
    if not beats:
        return ["VURUS_YOK"]
    slots = _slots(fmt)
    total = seconds or sum(_dur(b) for b in beats)
    lo, hi = fmt.get("hedef_sure_sn", [0, 10 ** 9])
    if total < lo:
        errs.append("SURE_KISA: %.0f sn < formül alt sınırı %d sn" % (total, lo))
    seq, by_slot, unknown = [], {}, 0
    for i, b in enumerate(beats):
        s = b.get("formula_slot")
        if s not in slots:
            unknown += 1
            continue
        by_slot.setdefault(s, []).append(i)
        if not slots[s].get("serbest") and (not seq or seq[-1] != s):
            seq.append(s)
    if unknown:
        errs.append("SLOT_ETIKETI_YOK: %d vuruşta formula_slot boş ya da formülde yok" % unknown)
    order = [s["slot"] for s in fmt["yapi"] if not s.get("serbest")]
    firsts = [s for s in order if s in by_slot]
    first_pos = sorted(firsts, key=lambda s: min(by_slot[s]))
    if first_pos != firsts:
        errs.append("SIRA_BOZUK: bölümün akışı %s, formül %s" % (" > ".join(first_pos), " > ".join(firsts)))
    for s in fmt["yapi"]:
        n = len(by_slot.get(s["slot"], []))
        if s.get("zorunlu", True) and n == 0 and s["adet"][0] > 0:
            errs.append("SLOT_EKSIK: '%s' (%s) yok" % (s["slot"], s["ad"]))
            continue
        if s.get("serbest") and n and not (s["adet"][0] <= n <= s["adet"][1]):
            errs.append("SLOT_ADEDI: '%s' %d vuruş, %d-%d olmalı" % (s["slot"], n, s["adet"][0], s["adet"][1]))
        if s.get("pay") and n and total:
            share = sum(_dur(beats[i]) for i in by_slot[s["slot"]]) / total
            if not (s["pay"][0] <= share <= s["pay"][1]):
                errs.append("SURE_PAYI: '%s' bölümün %%%.0f'i, formül %%%.0f-%%%.0f" % (s["slot"], share * 100, s["pay"][0] * 100, s["pay"][1] * 100))
    roles = {c.get("id"): c.get("formula_role") for c in ((bible or {}).get("characters") or [])}
    for r in fmt.get("kurallar", []):
        k = r["tur"]
        if k == "once":
            idx = by_slot.get(r["once_slot"])
            before = [i for i in by_slot.get(r["slot"], []) if idx and i < min(idx)]
            if idx and len(before) < r["en_az"]:
                errs.append("KURAL_ONCE: '%s' öncesinde %d '%s' var, en az %d" % (r["once_slot"], len(before), r["slot"], r["en_az"]))
        elif k == "slot_rol" and bible:
            ok = any(roles.get(c) == r["rol"] for i in by_slot.get(r["slot"], []) for c in beats[i].get("characters", []) or [])
            if by_slot.get(r["slot"]) and not ok:
                errs.append("KURAL_ROL: '%s' vuruşlarında '%s' rolünden karakter yok" % (r["slot"], r["rol"]))
        elif k == "slot_karakter":
            cs = {c for i in by_slot.get(r["slot"], []) for c in beats[i].get("characters", []) or []
                  if not r.get("rol") or roles.get(c) == r["rol"]}
            if by_slot.get(r["slot"]) and (bible or not r.get("rol")) and len(cs) < r["en_az"]:
                errs.append("KURAL_KARAKTER: '%s' vuruşlarında %d farklı karakter, en az %d" % (r["slot"], len(cs), r["en_az"]))
        elif k == "diyalog_orani":
            q = sum(1 for b in beats if _has_dialogue(b)) / float(len(beats))
            if not (r["min"] <= q <= r["max"]):
                errs.append("KURAL_DIYALOG: diyaloglu vuruş %%%.0f, formül %%%.0f-%%%.0f" % (q * 100, r["min"] * 100, r["max"] * 100))
        elif k == "dakikada":
            n = len(by_slot.get(r["slot"], []))
            if total and n / (total / 60.0) < r["en_az"]:
                errs.append("KURAL_YOGUNLUK: dakikada %.2f '%s', en az %.1f" % (n / (total / 60.0), r["slot"], r["en_az"]))
        elif k == "alan_dolu":
            # "(varsayılan)" değeri senaryo odasının boşluğu kapatmak için koyduğu yer tutucudur, dolu sayılmaz
            bad = [i for i in by_slot.get(r["slot"], [])
                   if not str(beats[i].get(r["alan"]) or "").strip() or "(varsayılan)" in str(beats[i].get(r["alan"]))]
            if bad:
                errs.append("KURAL_ALAN: %d '%s' vuruşunda '%s' boş (ilk: %d)" % (len(bad), r["slot"], r["alan"], bad[0]))
        elif k == "motif_tekrar":
            cnt = {}
            for b in beats:
                m = _fold(b.get(r["alan"], "")).strip()
                if m:
                    cnt[m] = cnt.get(m, 0) + 1
            if not cnt or max(cnt.values()) < r["en_az"]:
                errs.append("KURAL_MOTIF: hiçbir şaka motifi %d kez tekrar etmiyor" % r["en_az"])
        elif k == "yasak_kelime":
            for i, b in enumerate(beats):
                text = _lower_tr(" ".join(str(b.get(x) or "") for x in ("action", "dialogue")))
                hit = [w for w in r["kelimeler"] if re.search(r"(^|\W)%s" % re.escape(_lower_tr(w)), text)]
                if hit:
                    errs.append("KURAL_GUVENLIK: vuruş %d '%s' içeriyor" % (i, hit[0]))
    return errs


def readiness(fmt, root=ROOT, report=None):
    """Formülün istediği motor yeteneklerinin durumu (engine_gaps'ten). Döner: {yetenek: durum, ..., 'eksik': [...]}."""
    sys.path.insert(0, HERE)
    import engine_gaps
    rep = report or engine_gaps.check(root)
    by = {r["id"]: r for r in rep["yetenekler"]}
    rows = []
    for cid in fmt.get("gerekli_yetenekler", []):
        r = by.get(cid)
        rows.append({"id": cid, "yetenek": r["yetenek"] if r else "?", "durum": r["durum"] if r else "HARITADA_YOK",
                     "insan_onayi": bool(r and r["insan_onayi"])})
    count = {}
    for r in rows:
        count[r["durum"]] = count.get(r["durum"], 0) + 1
    return {"format": fmt["id"], "ad": fmt["ad"], "gerekli": len(rows), "sayim": count, "yetenekler": rows,
            "eksik": [r["id"] for r in rows if r["durum"] in ("YOK", "KANIT_BOZUK", "HARITADA_YOK")]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dizi formülü motoru")
    ap.add_argument("--root", default=ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("liste")
    s = sub.add_parser("iskelet"); s.add_argument("format_id"); s.add_argument("--sure", type=float, default=480)
    d = sub.add_parser("denetle"); d.add_argument("format_id"); d.add_argument("beat_sheet"); d.add_argument("--bible")
    h = sub.add_parser("hazirlik"); h.add_argument("format_id", nargs="?")
    a = ap.parse_args(argv)
    if a.cmd == "liste":
        for fid in format_ids(a.root):
            f = load(fid, a.root)
            print("%s: %s (%s yaş, %d-%d sn)" % (fid, f["ad"], f["kitle_yasi"], f["hedef_sure_sn"][0], f["hedef_sure_sn"][1]))
        return 0
    if a.cmd == "iskelet":
        for x in skeleton(load(a.format_id, a.root), a.sure):
            print("%6.1f-%6.1f  %-18s %s" % (x["t0"], x["t1"], x["slot"], x["tanim"]))
        return 0
    if a.cmd == "denetle":
        sheet = json.load(open(a.beat_sheet, encoding="utf-8"))
        bible = json.load(open(a.bible, encoding="utf-8")) if a.bible else None
        fmt = load(a.format_id, a.root)
        errs = (cast_errors(bible, fmt) if bible else []) + episode_errors(sheet.get("beats", []), fmt, bible, sheet.get("total_seconds"))
        print("\n".join(errs) if errs else "FORMUL_UYUMLU (yapı denetimi; yaratıcı kalite sahibin onayıdır)")
        return 1 if errs else 0
    if a.cmd == "hazirlik":
        for fid in ([a.format_id] if a.format_id else format_ids(a.root)):
            r = readiness(load(fid, a.root), a.root)
            print("%s: %d yetenek | %s | eksik: %s" % (r["ad"], r["gerekli"], ", ".join("%s %d" % kv for kv in sorted(r["sayim"].items())),
                                                        ", ".join(r["eksik"]) or "-"))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
