---
name: studio-cinematic-video
description: Referans kontrollü sinematik video motorunu güvenli, ücret kapılı ve doğrulanabilir çalıştırma
when_to_use: Gerçek video üretimi, kamera hareketi veya LTX/Wan benzeri motor karşılaştırması gerektiğinde.
---

# Studio Cinematic Video

## Ön koşul
- GPU/VRAM ve model cache gerçekten doğrulanır (`engine_inventory`).
- Kaynak görselin kimlik SHA'sı ve ticari lisansı kayıtlı.
- Ücretli sağlayıcı için owner approval + bütçe cap.

## Prosedür
1. Motoru provider registry'den seç; model adı koda gömülmez.
2. Workflow/prompt/seed/referans SHA'sını manifeste yaz.
3. Kısa test (2–4 sn) üret; video stream, süre, motion ve kimlik kontrolü yap.
4. Başarılıysa planlı shot'ı üret; başarısızsa sınıflandır (GPU/OOM/timeout/invalid).
5. Alternatif motor yalnız aynı referans ve lisansla denenir; en fazla bir kez.

## Kabul
- Gerçek MP4; video stream >1 kare; süre ±0.5 sn.
- Yüz kimliği referanstan sapmıyorsa sahne kabul; sapıyorsa ret.
- Slayt, sabit arka plan veya başlık kartı teslim değildir.

## Yasak
- GPU yokken "çalıştı" demek.
- Ücretli pod/API'yi onaysız başlatmak.
- Tanıtım videosunu gerçek üretim kalitesi sanmak.
