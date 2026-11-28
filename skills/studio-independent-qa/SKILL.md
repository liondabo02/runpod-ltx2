---
name: studio-independent-qa
description: Üretimi yapan işçiden bağımsız teknik ve yaratıcı kalite denetimi; kanıta dayalı, fail-closed
when_to_use: Senaryo, ses, animasyon, render veya bölüm teslim edilmeden önce; her aşamanın çıktısı için.
---

# Studio Independent QA

## Kural
QA, işi yapan işçiden BAĞIMSIZDIR. Üretici kendi çıktısını onaylayamaz. Yaratıcı onay (beğeni) yalnız sahibindedir; QA "teknik PASS" ve "yaratıcı öneri" verir.

## Girdi
Aşama çıktısı + ilgili kanıt dosyaları (manifest, hash, ffprobe çıktısı).

## Teknik denetim (otomatik, ffmpeg/ffprobe)
- Çözünürlük/fps/süre hedefe uygun mu (480 sn ±2).
- Ses akışı var mı; ses seviyesi normalize mi.
- Donmuş kare oranı, titreme (flicker), kare sıçraması.
- Dosya hash'i manifestle eşleşiyor mu.
- Maliyet: aşama maliyetleri toplamı ≤ 1,00 EUR; ücretli çağrı sahibin onayıyla mı.

## Yaratıcı denetim (öneri)
`studio-screenwriting` rubriği (100 puan) ile beat bazında. Görüntü/ses görülmeden puan verilmez: "NOT_EVALUATED" yazılır.

## Kimlik ve süreklilik
Karakter yüzü/kıyafeti/sesi `series-bible.json` kilidiyle (hash) karşılaştırılır. Yeni yüz üretilmişse reddedilir.

## Hak ve lisans
Her varlığın `licence_status` alanı olmalı; bilinmeyen = RED.

## Çıktı: `quality_report.json`
`verdict` (PASS / NEEDS_REVISION / FAIL), `evidence` (dosya yolu + hash), `findings` (öncelik P0–P2), `cost_eur`, `creative: NOT_EVALUATED | SUGGESTION`.
Kanıtsız PASS yazılmaz. Eksik kanıt = NEEDS_REVISION.

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- QA-03 Diyalog kapsama kapısı (her replik seslendirildi) [KISMI]: `tools/dialogue_check.py` — açık: Q12
- QA-04 Sahne sözleşmesi ve süreklilik kapısı [KISMI]: `tools/continuity.py`, `tools/scene_contract.py` — açık: S1
- QA-05 Bilerek eklenmiş hataları yakalayan bağımsız QA [YOK]: araç yok — açık: Q1
- QA-06 2D kalite standardı ölçümü [VAR]: `tools/studio_standards_check.py`
<!-- MOTORLAR:BITIS -->
