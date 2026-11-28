---
name: studio-production-analytics
description: Üretim analitiği: geçme oranı, süre, onarım sayısı
when_to_use: Bölüm bitince veya haftalık; hangi işçi/aşama zayıf, görmek için.
---

# studio-production-analytics

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- kuyruk DB (salt okunur)
- worker memory jsonl

## Prosedür
1. Aşama başına geçme oranı, ortalama süre, onarım turu sayısını hesapla.
2. Gerilemeleri bul (önceki bölüme göre).
3. Bulguları ilgili işçinin 'ders' kaydına ve kılavuzuna öneri olarak yaz.
4. `analytics-report.json`.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Salt okunur erişim
- Uydurma metrik yok

## Yasak
- Veritabanına yazmak
- Doğrulanmamış rakam raporlamak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).
