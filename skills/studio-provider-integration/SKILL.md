---
name: studio-provider-integration
description: Model/sağlayıcı bağımlılığını config ve adapter sözleşmesiyle yönetme
when_to_use: Yeni TTS, görsel, video, LLM veya render motoru bağlanacağında.
---

# Studio Provider Integration

## Sözleşme
- `provider_id`, `task_types`, `languages`, `paid`, `external`, `commercial_default`, `priority`
- `adapter` ve `config_ref`; model/endpoint/fiyat koda gömülmez.
- Çağrı: `adapter(job, out_path) -> {path, engine, latency, cost, language}`.

## Prosedür
1. Kataloğa descriptor ekle; model bilgisini config'e koy.
2. Adapter'ı mevcut modüle kaydet; yeni üst düzey silo açma.
3. Sağlık kontrolü ve yetenek eşleşmesi yap.
4. Ücretsiz/yerel önce; ücretli yalnız açık approval + bütçe.
5. Gerçek çıktıyı doğrula; boş/yanlış dil/hatalı şema reddedilir.
6. Fallback zincirini tek yerde tanımla; en fazla bir alternatif.

## Kabul
- Aynı job farklı sağlayıcıyla kod değişmeden çalışır.
- Ücretli çağrı onaysız yapılmaz; karar loglanır.
- Sağlayıcı hatası sınıflandırılır: retry / fallback / block.
