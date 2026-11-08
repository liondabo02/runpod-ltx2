# P10 — Türkçe çocuk sesi denemesi ve engel

Durum: **BLOCKED** · gerçek çocuk sesi üretilemedi · sesli sahne yok

## Denenen mevcut kaynaklar

| Kaynak | Sonuç |
|---|---|
| Windows SAPI | Yalnız `Microsoft Hedda Desktop (de-DE)` ve `Zira Desktop (en-US)`; **Türkçe yok** |
| `edge-tts` (kurulu) | Çalıştı; Türkçe `tr-TR-EmelNeural` **yetişkin kadın** sesi |
| Kokoro | Paket kurulu değil; model yalnız İngilizce ağırlık; Türkçe desteklenmiyor |
| AHOS `core-voices/aden/tr.wav` | Jenerik referans; hedef replik değil, çocuk yaşı doğrulanmadı |
| Chatterbox / diğer HF TTS | Kurulu değil; ücretsiz/kimlik uygunluğu doğrulanmadı |

## Neden kullanılmadı?

- `tr-TR-EmelNeural` **yetişkin kadın**; hız/pitch ile "çocuk" yapmak yasak.
- Kaan için doğal bebek sesi üretecek doğrulanmış kaynak yok.
- Fonem/viseme zamanlaması olmadan gerçek lip-sync üretilemez.

## Sonuç

Türkçe çocuk sesi **yok**; dudak senkronu **yok**; sesli MP4 **yok**.
Sessiz teknik animasyon ayrı ve açıkça etiketli tutuluyor.
