# -*- coding: utf-8 -*-
"""AHOS uyarlama/ilham hattı (hak denetimli).
İki kip:
  --mode inspire  (varsayılan): kaynaktan YALNIZ soyut yapı çıkarır (perde dağılımı, karakter rolleri, mekân türleri, duygu eğrisi, tempo).
                  Replik, ad, olay örgüsü ayrıntısı taşınmaz. Çıktı: özgün senaryo yazımı için 'özgünleştirme kontrol listesi'.
  --mode adapt    : kaynağı AHOS senaryosuna çevirmeye hazırlar. YALNIZ --rights own|public_domain|licensed ve --proof (kanıt/lisans notu) ile.
                  'unknown' ise ret (çıkış kodu 2). Telif altındaki bir film/çizgi filmi küçük değişiklikle yeniden sunmak türev eserdir; yapılmaz.
Girdi: düz metin (senaryo, özet, altyazı .srt, transkript). Çıktı: <out>/adaptation_plan.json (+ adapt kipinde source_script.txt)."""
import argparse, json, os, re, sys, collections

PROTECTED_HINT = re.compile(r"\b(disney|pixar|warner|hanna|barbera|scooby|tom\s*&?\s*jerry|şirin|smurf|caillou|wildbrain|marvel|netflix)\b", re.I)


def clean_srt(t):
    t = re.sub(r"^\d+\s*$", "", t, flags=re.M)
    t = re.sub(r"\d\d:\d\d:\d\d[,.]\d+\s*-->\s*\d\d:\d\d:\d\d[,.]\d+", "", t)
    return re.sub(r"\n{2,}", "\n", t).strip()


def structure(text):
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n", text) if len(s.strip()) > 2]
    n = max(1, len(sents))
    acts = []
    for i, (a, b) in enumerate(((0, .25), (.25, .75), (.75, 1.0))):
        seg = sents[int(a * n):int(b * n)]
        q = sum(s.count("?") for s in seg); ex = sum(s.count("!") for s in seg)
        acts.append({"perde": i + 1, "cümle_payı": round(len(seg) / n, 2), "soru_oranı": round(q / max(1, len(seg)), 2), "ünlem_oranı": round(ex / max(1, len(seg)), 2)})
    names = collections.Counter(re.findall(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\b", text))
    top = [c for _, c in names.most_common(6)]
    roles = [{"rol": "R%d" % (i + 1), "ağırlık": round(c / max(1, sum(top)), 2)} for i, c in enumerate(top)]   # adlar bilerek taşınmaz
    place_kinds = {"ev/iç mekân": r"\b(oda|ev|mutfak|salon|house|room|kitchen)\b", "park/bahçe/doğa": r"\b(park|bahçe|orman|garden|forest|bataklık)\b",
                   "yol/sokak": r"\b(yol|sokak|street|road)\b", "su": r"\b(göl|nehir|deniz|lake|river|sea)\b"}
    places = [k for k, p in place_kinds.items() if re.search(p, text, re.I)]
    return {"toplam_cümle": n, "perdeler": acts, "karakter_rolleri": roles, "mekân_türleri": places}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-file", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["inspire", "adapt"], default="inspire")
    ap.add_argument("--rights", choices=["own", "public_domain", "licensed", "unknown"], default="unknown")
    ap.add_argument("--proof", default="")
    a = ap.parse_args()
    text = open(a.source_file, encoding="utf-8", errors="ignore").read()
    if a.source_file.lower().endswith(".srt"):
        text = clean_srt(text)
    os.makedirs(a.out, exist_ok=True)
    plan = {"mod": a.mode, "hak_durumu": a.rights, "kanıt": a.proof, "yapı": structure(text)}
    if a.mode == "adapt":
        if a.rights == "unknown" or not a.proof.strip():
            print("RET: uyarlama için hak durumu own|public_domain|licensed ve --proof (kanıt/lisans notu) zorunlu. Telifli yapımın küçük değişiklikle yeniden sunumu yapılmaz. 'inspire' kipini kullanın.")
            return 2
        if PROTECTED_HINT.search(text + " " + a.proof) and a.rights != "licensed":
            print("RET: metin bilinen telifli bir yapıma işaret ediyor; yalnız 'licensed' ve yazılı lisans kanıtıyla ilerlenir.")
            return 2
        open(os.path.join(a.out, "source_script.txt"), "w", encoding="utf-8").write(text)
        plan["kredi"] = "Uyarlama; kaynak hakkı: %s (%s)" % (a.rights, a.proof)
        plan["sonraki"] = "script_to_beats.py + script_enrich.py; sonra 30-60 sn kabul sahnesi"
    else:
        plan["özgünleştirme_kontrol_listesi"] = [
            "Karakter adlarını, görünüşlerini ve ses tarzlarını tamamen yeni yaz",
            "Olay örgüsünü birebir izleme: yalnız perde ritmini ve duygu eğrisini örnek al",
            "Replikleri, ünlü sahneleri ve gag'leri kullanma",
            "Mekân, zaman ve çatışmayı yeni bir fikre taşı",
            "Referanstan yalnız ışık/kamera/tempo ilkelerini al (docs/GORSEL_YONETMEN_KURALLARI.md)"]
    json.dump(plan, open(os.path.join(a.out, "adaptation_plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TAMAM", a.mode, os.path.join(a.out, "adaptation_plan.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
