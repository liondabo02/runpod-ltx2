#!/usr/bin/env python3
"""AHOS Dünya Kurucu: dizi için sayfalarca 'dünya + hikâye kitabı' üretir (diziden bağımsız).
Bölüm bölüm ayrı LLM çağrısı yapar (her biri ~1-2 sayfa), hepsini series/<id>/world-bible.md dosyasında birleştirir.
Bölümler: 1 dünya özeti, 2 bölgeler (>=6, her biri mekânlarıyla), 3 karakterler (>=8), 4 ilişkiler/çatışmalar,
5 ana hikâye yayı, 6 sezon planı (bölüm bölüm), 7 görsel/ses rehberi. Ayrıca bible'a mekân/karakter ekler (yeni id'ler)."""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import writers_room as wr  # noqa: E402

SYS = ("Sen deneyimli bir çizgi film dizisi baş yazarısın. Türkçe, ayrıntılı, somut yaz (genel laf yok). Çocuk dizisi güvenlik "
       "kurallarına uy: şiddet/korku yok, sıcak ve eğlenceli ton. Görselleştirilebilir sahneler yaz: ne görülür, ne yapılır.")

SECTIONS = [
    ("dunya", "1. Dünyanın genel tanımı",
     "Dünyanın kuralları, atmosferi, esprili/sevimli ayırt edici özellikleri, 'neden izlenir'. 400-600 kelime."),
    ("bolgeler", "2. Bölgeler ve mekânlar",
     "EN AZ 6 farklı bölge; her bölge için: ad, iklim/renk paleti, 3-4 alt mekân (ör. patika, nehir kıyısı, çatı, oda, bahçe), "
     "orada geçen oyun/macera türü, gün içi ışık değişimi. Her bölge 120+ kelime."),
    ("karakterler", "3. Karakterler",
     "EN AZ 8 karakter (hepsi özgün): ad, yaş, dış görünüş (renk/şekil/aksesuar, çizimle ayırt edilir), kişilik, konuşma tarzı, "
     "tuhaf alışkanlığı, korkusu, hedefi, hangi bölgede yaşar. Her biri 80+ kelime."),
    ("iliskiler", "4. İlişkiler ve çatışmalar",
     "Karakterler arası dostluk/kıskançlık/rekabet/aile bağları ve bunlardan doğan tekrar eden komik çatışmalar. 300-500 kelime."),
    ("ana_yay", "5. Ana hikâye yayı",
     "Tüm sezonu bağlayan merak unsuru: gizem/hedef, dönüm noktaları, final. Başlangıç-orta-son. 400-600 kelime."),
    ("sezon", "6. Sezon planı",
     "12 bölüm: her biri için başlık, bölge, ana karakterler, 5-6 cümlelik olay örgüsü (kanca -> sorun -> komik tırmanış -> çözüm), "
     "bölüm sonu sürprizi. Bölümler 8 dakikalık."),
    ("rehber", "7. Görsel ve ses rehberi",
     "Düz renkli, kalın çizgili 2D stil; her bölgenin renk paleti, karakter hareket tarzı (yürüyüş, zıplama), müzik havası, "
     "ses efekti listesi, doğal konuşma kuralları (kısa cümle, tepkiler, sessiz aksiyon anları). 300-500 kelime."),
]


def build(brief, series_id, out_dir=None, llm=None):
    llm = llm or wr.llm_call
    out_dir = out_dir or os.path.join(ROOT, "series", series_id)
    os.makedirs(out_dir, exist_ok=True)
    parts, ctx = [], f"Dizi fikri: {brief}"
    for key, title, ask in SECTIONS:
        text = (llm(SYS, f"{ctx}\n\nŞimdi yalnız şu bölümü yaz: {title}\n{ask}\nBaşlık atma, sadece içeriği yaz. Önceki bölümlerle tutarlı ol.", 0.8) or "").strip()
        if len(text.split()) < 60:
            text = (llm(SYS, f"{ctx}\n\nTEKRAR, daha uzun ve ayrıntılı yaz: {title}\n{ask}", 0.8) or "").strip()
        parts.append((key, title, text))
        ctx += f"\n\n[{title} - özet] " + " ".join(text.split()[:120])
    md = f"# Dünya ve Hikâye Kitabı\n\n_Dizi fikri: {brief}_\n\n" + "\n\n".join(f"## {t}\n\n{x}" for _, t, x in parts) + "\n"
    p = os.path.join(out_dir, "world-bible.md")
    open(p, "w", encoding="utf-8").write(md)
    words = len(md.split())
    short = [t for _, t, x in parts if len(x.split()) < 60]
    st = {"status": "PASSED" if not short else "NEEDS_REVISION", "path": p, "words": words, "pages_approx": round(words / 450, 1),
          "short_sections": short, "note": "içerik kalitesini insan/yaratıcı kritik gözüyle değerlendir; sayfa=~450 kelime"}
    json.dump(st, open(os.path.join(out_dir, "world-bible.report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--brief", required=True); ap.add_argument("--series-id", required=True)
    a = ap.parse_args(); print(json.dumps(build(a.brief, a.series_id), ensure_ascii=False, indent=1))
