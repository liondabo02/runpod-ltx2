# Araç araştırması (ses motoru) — 23 Kasım 2026
Kaynak: [Open-Source Turkish TTS survey](https://danielquillanroxas.github.io/turkish-tts-survey), [Piper tr_TR voices](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/tr/tr_TR).
Bu tablo anket sayfasının lisans bilgisidir; kullanmadan önce her modelin kendi model kartı ayrıca doğrulanmalıdır (anket bazı lisansları çelişkili bildiriyor).

| Model | Lisans (ankete göre) | Ticari kullanım | Boyut | Not |
|---|---|---|---|---|
| Piper tr_TR-dfki | MIT | evet | 63 MB | Tek Türkçe Piper sesi, CPU'da çalışır; tek ses, duygu yok |
| F5-TTS Türkçe (Karayakar) | MIT | evet | 4,1 GB | Ses klonlama; karakter başına referans ses gerekir; GPU önerilir |
| Orkhon-TTS (F5) | Apache 2.0 | evet | 3,4 GB | Alfa; klonlama |
| Orpheus-TR GGUF (Karayakar) | MIT | evet | 2,4 GB | CPU'da çalışan nicemlenmiş sürüm; kahkaha/iç çekme etiketleri |
| facebook/mms-tts-tur | CC-BY-NC | **hayır** | 145 MB | Ticari yayında kullanılamaz |
| marduk-ra F5-Turkish | CC-BY-NC | **hayır** | 4,1 GB | — |
| XTTS-v2 (karagoz-hacivat) | CC-BY-NC-SA | **hayır** | 3,8 GB | — |
| edge-tts (şu an) | Microsoft hizmeti | **sahip kararı gerekli** | bulut | yalnız 2 Türkçe ses |

## Sonuç
- Şu anki CPU makinede en güvenli yol: Piper tr_TR-dfki (MIT) + mevcut edge sesleri; ikisi de tek karakter başına sınırlı çeşitlilik verir.
- Karakter başına gerçekten farklı, duygulu ses için: F5-TTS Türkçe (MIT) veya Orpheus-TR GGUF (MIT). Bunlar indirme (2–4 GB) ve model kurulumu ister. İndirme sahibin onayına bağlıdır (kural: indirmek için dosya adı, kaynak ve boyut sorulur).
- Şu an bu makinede ağ erişimi yalnızca arama/okuma ile sınırlı olduğu için hiçbiri indirilmedi ve kurulu sayılmaz.
