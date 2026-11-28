---
name: studio-localisation-delivery
description: Dil sürümleri, altyazı ve teslim paketi
when_to_use: Bölüm onaylandıktan sonra TR/DE vb. sürümler ve teslim için.
---

# studio-localisation-delivery

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- onaylı bölüm mp4
- diller
- metadata

## Prosedür
1. Her dil için ayrı ses izi; altyazı .srt üret.
2. Çeviri doğallığı: kelimesi kelimesine değil, çocuk diline uygun yeniden yaz.
3. Akışları ve senkronu doğrula (altyazı < 200 ms).
4. Teslim paketi: mp4, srt, manifest, lisans dosyası. Yayınlama YOK (sahip onayı).

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Ses+video akışı
- Altyazı senkron
- Kurmancî izi: PENDING olarak işaretli

## Yasak
- Sahip onayı olmadan yayınlamak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- YER-01 Çeviri ve dil dizini (süre bütçesiyle) [VAR]: `tools/localisation_worker.py`
- YER-02 Her hedef dil için lisansı uygun yerel ses motoru [VAR, insan onayı]: `tools/localisation_worker.py`
<!-- MOTORLAR:BITIS -->
