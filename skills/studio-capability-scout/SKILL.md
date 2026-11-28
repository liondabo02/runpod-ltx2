---
name: studio-capability-scout
description: Yeni motor/araç keşfi; uygulamadan öneriye
when_to_use: Üretimde tekrarlanan bir başarısızlık veya yetenek boşluğu olduğunda.
---

# studio-capability-scout

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- görev hataları
- motor envanteri
- izin verilen kaynaklar (watchlist.json)

## Prosedür
1. Boşluğu tanımla (hangi aşama, hangi hata).
2. En az 3 aday karşılaştır: lisans, donanım, maliyet, risk.
3. Hiçbir şeyi kendi başına indirme/kurma/harcama; öneri + kanıt sahibe gider.
4. `capability-proposals.json` yaz.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Her öneri gerçek kaynağa dayalı
- Lisans riski belirtilmiş
- Ücretli benimseme sahip onaylı

## Yasak
- Kaynaksız öneri
- Otomatik kurulum
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- YAZ-01 Motor yetenek/skill eksik envanteri [VAR]: `tools/engine_gaps.py`
<!-- MOTORLAR:BITIS -->
