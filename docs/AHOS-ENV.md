# AHOS çekirdek ortam değişkenleri

Bu dosya `ahos_core` için geçerlidir (RunPod worker'ının `.env.example` dosyası ayrıdır).
Hiçbiri zorunlu değildir; her biri kapalıyken güvenli varsayılana düşer.

## Model / yürütücü

| Değişken | Varsayılan | Etki |
|---|---|---|
| `AHOS_EXECUTOR` | `deterministic` | `model` → LLM yürütücüsü, `deterministic` → kodsal yürütücü |
| `AHOS_LLM_BASE_URL` | — | OpenAI uyumlu uç (tünel `http://127.0.0.1:11500/v1` gibi) |
| `AHOS_LLM_MODEL` | `qwen2.5-coder:7b` | Model kimliği |
| `AHOS_LLM_API_KEY` | `local-only` | Anahtar (ücretli uçta sahip onayı gerekir) |
| `AHOS_LLM_FREE` | `1` | Ücretsiz kaynak işareti; ücretli çağrı ayrıca onay ister |
| `AHOS_ALLOW_PAID_LLM` | `0` | `1` olmadan ücretli çağrı reddedilir |
| `AHOS_PROVIDER_CHAIN` | `0` | `1` → sağlayıcı zinciri + çalışırlık ön kontrolü |

## Üretim/departman politikaları

| Değişken | Varsayılan | Etki |
|---|---|---|
| `AHOS_REQUIRE_PRODUCTIVE_CHANGE` | `0` (daemon açar) | Üretim adımı dosya değiştirmediyse `completed` reddedilir |
| `AHOS_ACCEPTANCE_ALLOW_UNTRACKED` | `0` | Git dışı projede kabul kapısı sabitlemeye açık izin |
| `AHOS_AUTO_APPROVE_RISK` | — | `medium` → orta riskli değişiklikler otomatik onaylanır |
| `AHOS_MODEL_PRODUCE_ONLY` | `1` | Yalnız `produce` adımı modeli kullanır |

## Çizgi film / ses

| Değişken | Varsayılan | Etki |
|---|---|---|
| `AHOS_VOICE_ENGINE` | otomatik | `edge` \| `piper` \| `sapi` — açık istek her zaman kazanır |
| `AHOS_PIPER_VOICE` | — | Yerel piper `.onnx` model yolu (varsa `edge` yerine de kullanılabilir) |
| `AHOS_BROWSER_QA` | `1` | Web projelerinde başsız tarayıcı duman testi |
| `AHOS_MISSION_TIMEOUT_SECONDS` | `900` | Görev süre sınırı |

## Depolama / veritabanı

| Değişken | Varsayılan | Etki |
|---|---|---|
| `AJAN_DATA` / `--runtime-dir` | `ahos_core/runtime` | Çalışma dizini (kuyruk DB'si, kanıtlar) |
| `DATABASE_URL` | — | Postgres'e geçiş (şema `migrate` ile uygulanır) |
| `AHOS_RUNPOD_ENABLED` | `0` | `1` olmadan GPU işi gönderilmez |
| `AHOS_RUNPOD_ENDPOINT` | — | RunPod serverless uç kimliği |
| `RUNPOD_API_KEY` | — | RunPod anahtarı (gerçek harcama → sahip onayı) |

## Güvenlik notları

- Hiçbir anahtar repoya yazılmaz; `.env` / ortam değişkeni olarak verilir.
- Ücretli model veya GPU çağrısı varsayılan olarak **kapalıdır** (`AHOS_ALLOW_PAID_LLM=0`, `AHOS_RUNPOD_ENABLED=0`).
- Ağ erişimi yalnız `clone-capture` hattına ve açık allowlist'e açıktır.
