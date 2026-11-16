---
name: studio-voice-lipsync
description: Karaktere özel ses kimliği, gerçek WAV ve fonem/viseme tabanlı dudak senkronu prosedürü
when_to_use: Diyalog, anlatım, dublaj veya ağız-ses eşleşmesi gerektiğinde.
---

# Studio Voice & Lip-sync

## Girdi
- `core_cast_voice_catalog.py` karakter ses yönü
- Diyalog metni, dil, duygu
- Sağlayıcı kaydı: ücretsiz/yerel önce; ücretli yalnız açık onayla

## Prosedür
1. `AudioProviderRegistry` ile dil + yetenek + lisans filtresi uygula.
2. Kalıcı `voice_id` seç; aynı karakter için değiştirme.
3. Gerçek WAV üret; süre, RMS ve dil eşleşmesini doğrula.
4. Fonem zamanlarını hizala (forced alignment); viseme tablosuna çevir.
5. Ağız kontrolünü viseme zaman çizelgesine bağla.
6. Kaymayı ölç: konuşma başı, sessizlik, kapanış.

## Kabul
- WAV gerçek ve boş değil; süre diyalogla uyumlu.
- Viseme JSON'da zaman damgaları var; ses-ağız kayması ≤80 ms.
- Çocuk sesi yoksa yetişkin ses "geçici/onaysız" etiketlenir; final sayılmaz.

## Yasak
- Yetişkin sesi pitch ile inceltip "doğal çocuk sesi" demek.
- Sessiz videoyu sesli teslim saymak.
- Lisansı belirsiz ses modeli kullanmak.
