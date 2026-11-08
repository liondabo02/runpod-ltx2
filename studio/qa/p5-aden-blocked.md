# P5 — Aden görsel adayı ve 5 sn animasyon: BLOCKED

Durum: **BLOCKED** · görsel adayı **üretilmedi** · animasyon **üretilmedi** · harcama 0 EUR

## Neden?

| Gereksinim | Gerçek durum |
|---|---|
| Onaylı Aden referansı | **0/16 APPROVED**; model sheet `NEEDS_REVISION` |
| Mevcut keyframe | 1280×720, SHA `b62eb34a…`; **yıldız toka ve 3 çil yok** → referans olamaz |
| ZeroGPU / Kontext | **Kota kapalı** (P2/P3 ölçümü; tekrar denenmedi) |
| Yerel görsel modeli | SDXL/Kontext/IP-Adapter **yok**; HF cache yalnız zeroscope + Kokoro |
| GPU / Blender | CUDA yok, Blender yok |
| Pollinations | Yalnız `sana` metin→görsel; kimlik/referans kontrolü yok |
| 3D mesh/rig | **Yok**; gerçek 3D animasyon üretilemez |

## Karar

- Yeni Aden yüzü **uydurulmadı**, mevcut yüz değiştirilmedi.
- Onaysız bir yüzü "Aden" diye animasyona sokmak kimlik riski olduğu için yapılmadı.
- 5 sn karakter animasyonu **yok**; 3D veya 2D cutout üretildiği iddia edilmiyor.

## Kanıt

- `studio/qa/p5-aden-gate.json` — marker kontrolü + engel listesi.
- `studio/qa/aden-reference-review.md` — keyframe'in kanon eksikleri.
- `studio/integration/openmontage-inventory.json` — kaynak/araç envanteri.

## Açılması için gereken

1. Sahip onaylı Aden v2 görseli **veya**
2. Kimlik koruyan, ücretsiz, yerel/erişilebilir bir üretici (ör. onaylı IP-Adapter hattı) **ve**
3. Sahibin "aday üret" onayı.

Bu koşullar sağlanmadan P5 üretimi başlatılmayacak.
