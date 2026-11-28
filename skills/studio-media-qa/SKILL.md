---
name: studio-media-qa
description: Video/ses/karakter kalitesini fail-closed ve kanıta dayalı denetleme prosedürü
when_to_use: Her render, ses, lip-sync veya bölüm teslimi öncesinde.
---

# Studio Media QA

## Kontroller
- Dosya var, boş değil, SHA-256 doğru.
- ffprobe: video/audio stream, çözünürlük, fps, süre.
- Motion: örneklenen karelerde gerçek değişim; statik slayt FAIL.
- Cut: beklenen sahne geçişi aralığında.
- Audio: stream + RMS/loudness; sessizlik FAIL.
- Duration: senaryo süresi ±0.5 sn.
- Lip-sync: viseme zamanı ile ses zamanı ≤80 ms.
- Identity: referans SHA + yüz benzerliği; ölçüm yoksa PASS verme.
- License: kaynak/model/çıktı ticari kullanımı kayıtlı.

## Çıktı
Makine-okur JSON: her kontrol için `ok`, sayısal değer, eşik, gerekçe.
`passed = all(checks)`; insan/yaratıcı onay ayrı alan.

## Yasak
- Eşiği düşürerek PASS üretmek.
- Ölçüm yokken tahmini puan vermek.
- Teknik PASS'i profesyonel kalite sanmak.

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- QA-01 Video teknik denetimi [VAR]: `tools/video_qa.py`
- QA-02 Ses teknik denetimi (konuşma, seviye) [VAR]: `tools/audio_qa.py`
- QA-07 Parçalı üretimde ses/kare sürekliliği [YOK]: araç yok — açık: Q11
<!-- MOTORLAR:BITIS -->
