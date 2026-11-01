# Kod modeli seçimi — araştırma ve karar

Tarih: 2026-11-01 · Sorun: yerel `qwen2.5-coder:7b` kod görevlerinde yetersiz
(`oyun → software` devri `failed`).

## Araştırma özeti (2026)

| Sağlayıcı | Model | Ücret | Limit | Not |
|---|---|---|---|---|
| Yerel (ollama) | qwen2.5-coder:7b | 0 $ | donanım | 0 $, çevrimdışı, küçük düzenlemeler |
| **NVIDIA NIM** (ücretsiz kademe) | `qwen/qwen3-coder-480b-a35b-instruct` | **0 $** (kredi) | 40 istek/dk | 480B sınıfı; **ajanlı kod için eğitilmiş**; araç çağrısı doğrulandı |
| NVIDIA NIM | `moonshotai/kimi-k2-instruct` | 0 $ (kredi) | 40 istek/dk | ikinci yedek, araç seçimi kararlı |
| OpenRouter `:free` | `qwen/qwen3-coder:free` | 0 $ | ~200 istek/gün/model | kota dolunca 429 |
| OpenRouter `:free` | `openai/gpt-oss-120b:free` | 0 $ | ~200 istek/gün | farklı sağlayıcı → 429'u atlatır |
| DeepSeek (ücretli) | DeepSeek V4 Flash | ~0,25 $/M çıktı | — | "kahve fiyatı" sınıfı, güçlü kod |
| DeepSeek (ücretli) | DeepSeek Coder | ~0,25 $/M | — | koda özel |
| Qwen (ücretli) | Qwen3-Coder-30B | ~0,35 $/M | — | kod uzmanı |
| DeepSeek (ücretli) | DeepSeek-R1 | ~2,50 $/M | — | derin akıl yürütme, pahalı |

Kaynaklar: [NIM/OpenRouter ücretsiz kademe rehberi](https://github.com/zephel01/CodeRouter/blob/main/docs/guides/free-tier-guide.en.md),
[2026 kod modeli karşılaştırması](https://dev.to/rileykim/the-developers-guide-to-picking-the-right-ai-code-model-in-2026-i-spent-500-so-you-dont-have-to-49a7),
[Qwen3-Coder model sayfası](https://openrouter.ai/qwen/qwen3-coder-480b-a35b-07-25%3Afree).

## Karar: tek model değil, **katmanlı yedekleme**

`ahos/model_registry.py` bu zinciri uygular:

```
1. local      (0 $, çevrimdışı)        → küçük düzenlemeler
2. nim        (0 $, 40 istek/dk)       → 480B sınıfı, ajanlı kod  ← asıl çözüm
3. openrouter (0 $, ~200/gün)          → kota yedekleri (farklı sağlayıcı)
4. deepseek   (~0,25 $/M, yalnız izin)  → son çare
```

Seçim görev sınıfına göre yapılır (`code` / `document` / `general`), anahtarın
varlığına ve **erişilebilirliğe** bakar (`GET /models`, ücret oluşturmaz), sonucu
mevcut yürütücü değişkenlerine yazar:

```
AHOS_LLM_BASE_URL · AHOS_LLM_MODEL · AHOS_LLM_API_KEY · AHOS_LLM_FREE
```

Ücretli sağlayıcı yalnızca `AHOS_ALLOW_PAID_LLM=1` iken seçilir.

## Kurulum (ücretsiz, kredi kartı gerekmez)

1. **NVIDIA NIM** — [build.nvidia.com](https://build.nvidia.com) → API anahtarı
   (`nvapi-...`) → `NVIDIA_NIM_API_KEY` olarak tanımla.
2. **OpenRouter** — [openrouter.ai/keys](https://openrouter.ai/keys) →
   `sk-or-v1-...` → `OPENROUTER_API_KEY` (yalnız `:free` SKU'lar).
3. Uygula:

```bash
python -m ahos.model_registry --choose code --apply
python -m ahos.model_registry --status
```

## Ölçüm planı (kanıt)

Aynı üç görev (fonksiyon ekle, hata düzelt, test yaz) her sağlayıcıda çalıştırılır;
başarı oranı, süre ve maliyet kaydedilir. Karar bu tabloya göre verilir, iddiaya göre değil.

## Diğer açık uçlar için araştırma notları

| Sorun | Çözüm | Lisans | Not |
|---|---|---|---|
| Gerçek dudak senkronu | **Whisper** forced alignment | MIT | kelime bazlı zamanlama → ağız hareketi |
| Kurgu uyumu | **OpenTimelineIO** | Apache-2.0 | EDL'den zengin, geri okunabilir timeline |
| 2D rig | OpenToonz / Inkscape + parçalı karakter | BSD/GPL | kol-bacak ayrı animasyon |
| Gerçek oyun | **Godot 4** | MIT | sahne + asset üretimi |
| Test kapsamı | **coverage.py** | Apache-2.0 | `pytest --cov` |
| Offsite yedek | **restic** + rclone | BSD/MIT | şifreli, artımlı, uzak depo |
| Sinematik video | LTX-2 (RunPod) | kendi lisansı | GPU kirası |
