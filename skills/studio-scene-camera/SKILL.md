---
name: studio-scene-camera
description: Mekân, ışık ve kamera planlama; sahne sürekliliği
when_to_use: shot_plan'dan sahne kurulurken; mekân/ışık/kamera kararlarında.
---

# studio-scene-camera

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- beat_sheet.json
- bible.locations
- ışık-saat kuralları

## Prosedür
1. Her mekân için ışık-saat tablosunu bible'dan oku; vuruşlar arası ışık yönü tutarlı olmalı.
2. Her vuruş için çekim ölçeği ve açı seç (geniş/orta/yakın); duygu yoğunluğu → çekim boyutu.
3. 3 farklı kadraj/kamera hareketi öner; bağımsız QA seçer.
4. Mekân geçişlerinde köprü planı ekle; sahne dışı prop yok.
5. Zemin kesişmesi ve kadraj dışı karakter testi.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Her vuruş kadrajlı
- Işık sürekliliği
- Zemin kesişmesi yok
- Kamera yalnız hikâyeyi destekliyor (gereksiz hareket yok)

## Yasak
- Sabit kadrajla süre doldurmak
- Bible dışı mekân
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- MEK-01 Çok katmanlı mekân (arka + ön plan) [VAR]: `tools/scenes2d.py`
- MEK-02 Kamera hareketinde katman paralaksı [YOK]: araç yok
- MEK-03 Senaryodaki ışık/gün saatine göre mekân [TESTSIZ]: `tools/scenes2d.py`
- MEK-04 Renk betiği (sahne duygusuna göre ton) [YOK]: araç yok
- MEK-05 Atmosfer parçacıkları ve ışık huzmesi [VAR]: `tools/fx_layer.py`
- KAM-01 Plan türleri (geniş/orta/yakın/tepki) [VAR]: `tools/shot_planner.py`
- KAM-02 Takip planı, kamera atlaması kapısı [VAR]: `tools/readability.py`
- KAM-03 Tepki planı [KISMI, insan onayı]: `tools/readability.py` — açık: K1i
- KAM-04 Kadraj ve baş payı (kazara kesme yok) [KISMI]: `tools/readability.py` — açık: Y2b
- KAM-05 Aksiyon okunabilirliği ölçü ve kapısı [VAR]: `tools/readability.py`
- KAM-06 Örtme bloklaması (oyuncular birbirini kapatmaz) [KISMI]: `tools/action_staging.py` — açık: Y1b, K1f
- KAM-07 Kurgu ritmi (çok kısa çekim yok, plan çeşitliliği) [VAR]: `tools/readability.py`
- KAM-08 Derinlik (z) ve storyboard sahnelemesi [YOK]: araç yok — açık: K1f
<!-- MOTORLAR:BITIS -->
