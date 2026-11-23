# -*- coding: utf-8 -*-
"""Özgünlük denetimi: yeni senaryo/dizi metninin bir ilham kaynağına (transkript, özet, senaryo) ne kadar benzediğini ölçer.
Ölçüler: (1) ortak özel adlar, (2) ortak 5'li kelime dizileri (replik/anlatım kopyası), (3) ortak 3'lü dizi oranı (anlam kalıbı).
Eşik aşılırsa çıkış kodu 3 ve 'yeniden yaz' raporu verir. Bu bir hukuki karar değildir; kopya riskini erken yakalayan bir önlemdir.
Kullanım: python tools/originality_check.py --new yeni_senaryo.txt --inspiration kaynak.txt [--out rapor.json]"""
import argparse, json, re, sys

NAME = re.compile(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\b")


def words(t):
    return re.findall(r"[a-zçğıöşü0-9]+", t.lower())


def grams(w, n):
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def check(new, insp, max_names=0, max_g5=0, max_g3=0.12):
    nn = set(NAME.findall(new)) & set(NAME.findall(insp))
    wn, wi = words(new), words(insp)
    g5 = grams(wn, 5) & grams(wi, 5)
    a3, b3 = grams(wn, 3), grams(wi, 3)
    r3 = len(a3 & b3) / max(1, len(a3))
    rep = {"ortak_özel_ad": sorted(nn)[:20], "ortak_5li_dizi": len(g5), "ortak_3lü_oran": round(r3, 3),
           "örnek_5li": [" ".join(g) for g in list(g5)[:5]]}
    rep["karar"] = "GEÇTİ" if (len(nn) <= max_names and len(g5) <= max_g5 and r3 <= max_g3) else "YENİDEN_YAZ"
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True); ap.add_argument("--inspiration", required=True); ap.add_argument("--out")
    a = ap.parse_args()
    rep = check(open(a.new, encoding="utf-8", errors="ignore").read(), open(a.inspiration, encoding="utf-8", errors="ignore").read())
    if a.out:
        json.dump(rep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep["karar"] == "GEÇTİ" else 3


if __name__ == "__main__":
    sys.exit(main())
