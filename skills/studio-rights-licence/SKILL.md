---
name: studio-rights-licence
description: Telif ve lisans geçidi; varlık menşei
when_to_use: Her varlık (model, ses, müzik, görsel) bölüme girmeden önce.
---

# studio-rights-licence

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- asset manifest'leri
- ses profilleri
- model lisansları

## Prosedür
1. Her varlık için kaynak, lisans, ticari kullanım durumunu yaz.
2. Bilinmeyen lisans = RED (varsayılan reddet).
3. Servis şartları belirsiz olanları (ör. edge-tts) 'review_required' işaretle; sahibe bildir.
4. Bilinen karakter/eser benzerliği taraması (isim, silüet, tema).

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Her varlıkta licence_status
- Yanlış ticari iddia yok

## Yasak
- Lisansı doğrulamadan 'ticari kullanılabilir' yazmak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- SEN-08 Özgünlük denetimi (bilinen esere benzerlik) [VAR]: `tools/originality_check.py`
<!-- MOTORLAR:BITIS -->
