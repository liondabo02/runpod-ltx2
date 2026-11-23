# -*- coding: utf-8 -*-
"""Senaryo ZENGİNLEŞTİRME: sahibin senaryosundaki replikler, süreler, sahneler ve karakterler AYNEN korunur; üzerine yalnız
motorun ekranda gösterebildiği ek 'yaşam' eklenir: dinleyen karakter tepkileri, arka planda küçük olaylar, çocuk mizahı (görsel şaka),
ses efekti, sahne içi hareket çeşitliliği. Yeni karakter, yeni replik, yeni mekân YOK. Her ek, sahip onayı için ayrı belgede listelenir.

İki katman: (1) kural tabanlı güvenli temel (LLM gerekmez, her zaman çalışır), (2) LLM varsa sahne başına daha yaratıcı öneriler (düz metin, JSON değil).
Kullanım: python tools/script_enrich.py <beat_sheet.json> <series-bible.json> <çıktı beat_sheet.json> [--no-llm]"""
import json, os, re, sys, threading
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

VOCAB_MOVES = "zıpla, koş, yürü, sarıl, el salla, dans et, gül, şaşır, uzan, göster, otur, eğil, bak, dinle, tut, kaldır"
VOCAB_PROPS = "uçurtma, balon, çiçek, yaprak, şişe, şapka, taş, fener, mikrofon"
VOCAB_SFX = "adım, koşu, zıplama, kapı, şaşkınlık, parıltı, rüzgâr, patlama"
LISTEN = ["{n} konuşanı dikkatle dinler, başını hafifçe sallar", "{n} gülümseyerek konuşana bakar", "{n} merakla öne eğilir ve dinler",
          "{n} küçük bir zıplamayla heyecanını gösterir", "{n} elini kaldırıp onaylar", "{n} şaşkın şaşkın bakar"]
IDLE_LIFE = ["{n} olduğu yerde hafifçe sallanır", "{n} etrafa merakla bakar", "{n} küçük bir adım atar ve geri döner"]
BABY_LIFE = ["{n} mırıldanarak kıpırdanır", "{n} küçük elini uzatır"]
BABIES = {"kaan", "medine", "ramin"}


def _name(c, bible):
    for ch in bible.get("characters", []):
        if ch["id"] == c:
            return ch.get("name", c)
    return c


def base_layer(sheet, bible):
    """Kural tabanlı güvenli zenginleştirme: her çekimde konuşmayan karakterlere tepki, sessiz çekimlere hayat."""
    out = []
    for i, b in enumerate(sheet["beats"]):
        speakers = set()
        for part in re.split(r"\s*\|\s*", b.get("dialogue") or ""):
            m = re.match(r"\s*([a-zçğıöşü0-9_]+)\s*:", part, re.I)
            if m: speakers.add(m.group(1).lower())
        adds = []
        quiet = [c for c in b.get("characters", []) if c not in speakers]
        for j, c in enumerate(quiet[:3]):
            n = _name(c, bible)
            tpl = (BABY_LIFE if c in BABIES else (LISTEN if speakers else IDLE_LIFE))
            adds.append(tpl[(i + j) % len(tpl)].format(n=n))
        out.append({"shot_id": b.get("shot_id"), "base": adds})
    return out


SYS = ("Sen deneyimli bir çocuk çizgi filmi yazarısın (2-5 yaş, sıcak, kural öğreten). Sana bir sahnenin çekim listesi verilecek. "
       "ASLA replik değiştirme, yeni karakter, yeni mekân ya da yeni replik ekleme. Yalnız her çekime EK görsel yaşam öner. "
       "Önerilerin motorun gösterebildiği fiillerle yazılsın. Fiiller: " + VOCAB_MOVES + ". Nesneler: " + VOCAB_PROPS + ". Ses: " + VOCAB_SFX + ". "
       "Çıktı biçimi: her çekim için TEK satır, başka hiçbir metin yazma:\n"
       "ÇEKİM <id> | TEPKİ: <sahnedeki bir karakterin kısa tepkisi, tek cümle> | ARKA: <arka planda küçük bir olay, tek cümle> | ŞAKA: <çocuk mizahı görsel şaka, tek cümle veya -> | SES: <efekt veya ->")


def _parse(text, valid_ids, cast_names):
    res = {}
    for ln in text.splitlines():
        m = re.match(r"\s*ÇEKİM\s+(\S+)\s*\|(.*)$", ln.strip(), re.I)
        if not m: continue
        sid = m.group(1).strip()
        if sid not in valid_ids: continue
        d = {}
        for part in m.group(2).split("|"):
            k, _, v = part.partition(":")
            k = k.strip().upper(); v = v.strip()
            if v and v != "-" and k in ("TEPKİ", "TEPKI", "ARKA", "ŞAKA", "SAKA", "SES"):
                d[{"TEPKI": "TEPKİ", "SAKA": "ŞAKA"}.get(k, k)] = v[:220]
        if d: res[sid] = d
    return res


def llm_layer(sheet, bible, scenes_parallel=4):
    try:
        import writers_room as wr
    except ImportError:
        return {}, "writers_room yok"
    by_scene = {}
    for b in sheet["beats"]:
        by_scene.setdefault(b["scene_id"], []).append(b)
    results, errors = {}, []
    lock = threading.Lock()

    def work(sc, beats):
        lines = []
        for b in beats:
            names = ", ".join(_name(c, bible) for c in b.get("characters", []))
            lines.append(f'- {b["shot_id"]} ({b["t_end"] - b["t_start"]:.0f} sn) [{names}] {b["action"]} || diyalog: {b.get("dialogue") or "-"}')
        user = f"Sahne {sc} (mekân: {beats[0]['location']}, ışık: {beats[0]['light_time']}).\nÇekimler:\n" + "\n".join(lines)
        try:
            txt = wr.llm_call(SYS, user, 0.8)
            r = _parse(txt, {b["shot_id"] for b in beats}, None)
            with lock: results.update(r)
        except Exception as e:  # noqa: BLE001
            with lock: errors.append(f"{sc}: {str(e)[:100]}")

    ths = []
    sc_list = list(by_scene.items())
    for k in range(0, len(sc_list), scenes_parallel):
        batch = sc_list[k:k + scenes_parallel]
        ths = [threading.Thread(target=work, args=a) for a in batch]
        for t in ths: t.start()
        for t in ths: t.join()
    return results, "; ".join(errors)


def enrich(sheet, bible, use_llm=True):
    base = {x["shot_id"]: x["base"] for x in base_layer(sheet, bible)}
    llm, err = ({}, "kapalı") if not use_llm else llm_layer(sheet, bible)
    names = {c["id"]: c.get("name", c["id"]).lower() for c in bible.get("characters", [])}
    out = json.loads(json.dumps(sheet)); report = []
    for b in out["beats"]:
        sid = b.get("shot_id"); adds = list(base.get(sid, [])); sfx = []
        extra = llm.get(sid, {})
        for k in ("TEPKİ", "ARKA", "ŞAKA"):
            if k in extra:
                txt = extra[k].rstrip(".")
                low = txt.lower()
                outsiders = [nm for cid, nm in names.items() if cid not in b.get("characters", []) and re.search(r"\b" + re.escape(nm), low)]
                if outsiders:          # sahnede olmayan karakter anılıyorsa öneri atılır (kanonu bozmasın)
                    continue
                adds.append(txt)
        if "SES" in extra:
            sfx.append(extra["SES"])
        orig_action = b["action"]
        if adds:
            b["action"] = orig_action.rstrip(".") + ". EK: " + ". ".join(a.rstrip(".") for a in adds) + "."
        if sfx:
            b["sound"] = (b.get("sound", "") + "; " + "; ".join(sfx)).strip("; ")
        b["enrichment"] = {"status": "PROPOSED_OWNER_APPROVAL_PENDING", "added": adds, "sfx": sfx}
        report.append((sid, orig_action, adds, sfx))
    out["status"] = "FROM_OWNER_SCRIPT_ENRICHED"
    out["enrichment_note"] = "replikler, süreler, sahneler, karakterler sahip senaryosundan AYNEN; yalnız 'EK:' kısımları yeni ve onay bekliyor"
    out["enrichment_llm"] = err or "tamam"
    return out, report


def write_report(report, path):
    L = ["# Senaryo zenginleştirme önerileri (sahip onayı bekler)", "",
         "Replikler, süreler, sahneler ve karakterler senaryodan **aynen** korunmuştur. Aşağıdaki satırlar yalnız eklenen görsel yaşamdır.", ""]
    for sid, orig, adds, sfx in report:
        if adds or sfx:
            L.append(f"- **{sid}**: {'; '.join(adds)}" + (f"  — ses: {', '.join(sfx)}" if sfx else ""))
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src, bib, dst = args[:3]
    sheet = json.load(open(src, encoding="utf-8")); bible = json.load(open(bib, encoding="utf-8"))
    out, rep = enrich(sheet, bible, use_llm="--no-llm" not in sys.argv)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_report(rep, os.path.splitext(dst)[0] + "_ENRICHMENT.md")
    print("zenginleştirildi:", sum(1 for r in rep if r[2]), "çekim; LLM:", out["enrichment_llm"])
