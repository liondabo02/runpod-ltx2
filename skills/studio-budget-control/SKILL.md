---
name: studio-budget-control
description: Aşama bazında maliyet takibi; bölüm başına ≤ 1,00 EUR
when_to_use: Her aşama bittiğinde ve herhangi bir ücretli çağrıdan önce.
---

# studio-budget-control

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- tüm aşamaların evidence JSON'ları
- maliyet politikası

## Prosedür
1. Her aşama `cost_eur` yazar; toplamı hesapla.
2. Ücretli çağrı = sahip onayı olmadan ENGEL.
3. Aşırım riski varsa daha ucuz yola (yerel render, ücretsiz kota) alternatif öner.
4. `budget-report.json` yaz.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Toplam ≤ 1,00 EUR
- Her ücretli işlem onaylı
- Maliyet uydurma yok (ölçülmemişse 'bilinmiyor')

## Yasak
- Tahmini maliyeti gerçek gibi yazmak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- URE-03 Ücretli çağrı engeli ve niyet kaydı [KISMI]: `tools/llm_guard.py` — açık: S3
- URE-04 Bölüm başı gerçek maliyet ölçümü (<= 1 EUR) [YOK]: araç yok
<!-- MOTORLAR:BITIS -->
