# AHOS devir teslim dosyası

Bu dosya, sistemi **başka bir araç veya kişi devraldığında** hiçbir bilginin
kaybolmaması için yazıldı. Her iddianın yanında onu **kendin doğrulayabileceğin**
komut var. Doğrulanamayan iddia yoktur.

## 1. Nerede ne var

| Yol | İçerik |
|---|---|
| `ahos_core/ahos/` | çekirdek modüller (182 dosya) |
| `ahos_core/tests/` | 192 test dosyası, 1142 test |
| `ahos_core/runtime/` | canlı durum: kuyruk DB'si, artefaktlar, raporlar, projeler |
| `ahos_core/tools/` | kurulum ve bakım araçları |
| `docs/` | analiz, stüdyo, ortam değişkenleri, bu dosya |
| `quality/evidence/` | üretim koşularının JSON kanıtları |

## 2. Sistemi çalıştırma

```bash
cd ahos_core
python -m pytest -q                     # tüm testler
python -m ahos.owner_cli "durum"        # holding durumu
python -m ahos.dashboard                # pano (Markdown + HTML)
python -m ahos.ops_cadence --once       # haftalık ritim turu
python -m ahos.owner_cli "çizgi film: parkta bir gün"   # bölüm üret
```

Kurulu komutlar: `ahos-owner`, `ahos-studio`, `ahos-cadence`, `ahos-panel`,
`ahos-daemon`, `ahos-ceo`, `ahos-status` (toplam 16).

## 3. İddiaları doğrulama tarifi

| İddia | Doğrulama |
|---|---|
| Testler geçiyor | `python -m pytest -q` → `1142 passed` |
| Departmanlar teslim edebilir | `python -m ahos.dashboard` → `16/16` |
| Bir görev gerçekten tamamlandı | `sqlite3 company-service.db "select mission_id,status,result_json from missions where mission_id='FIN-TEST-2'"` → `delivery.verified: true`, `qa_worker_ids` dolu |
| Sahte tamamlanma engelli | `python -m pytest tests/test_completion_db_guard.py -q` |
| Slayt video reddedilir | `python -m pytest tests/test_studio_2d.py -q` (`test_gate_rejects_a_static_slideshow`) |
| Türkçe ses çalışıyor | `python -m ahos.studio_pipeline --out /tmp/x --scenes 1 --seconds 2 "deneme"` → `acceptance.json` içinde `language_match: true` |
| Maliyet | `python -m ahos.dashboard` → `harcama: X $` (`model-spend.jsonl` toplamı) |

## 4. Bilinen açıklar (gizlenmiyor)

1. **Kod üretimi**: yerel `qwen2.5-coder:7b` karmaşık yazılım görevlerinde
   yetersiz; üretim adımı geçerli değişiklik çıkaramazsa görev `blocked` kalır.
   Daha güçlü model (veya RunPod'da 32B) bağlanınca aynı hat çalışır.
2. **Sinematik video**: `RUNPOD_API_KEY` yok; LTX-2 katmanı kapalı.
3. **CI**: bu makineden GitHub API'sine erişilemiyor; iş akışı sonucu
   görülemiyor. `git log` ve yerel testler tek doğrulama kaynağı.
4. **Eski kayıtlar**: guard'lar eklenmeden önce yazılmış 2.483 tutarsız satır
   bilinçli olarak değiştirilmedi (geçmişi yeniden yazmak kanıtı bozar).

## 5. Devralan için kurallar

- `completed` yalnızca proje kapısı + bağımsız QA geçerse yazılır; DB
  tetikleyicisi bunu zorlar. Elle SQL ile "completed" yazmak tetikleyiciye takılır.
- Ölçümü yükseltmek için kayıt düzenlenmez.
- Başka bir ajanın çalışma ağacındaki dosyaları ezme; `git reset --hard` yok.
- Yeni bir departman eklemek: `python tools/setup_department_workspaces.py`.
- Ücretli model/GPU varsayılan kapalı: `AHOS_ALLOW_PAID_LLM`, `AHOS_RUNPOD_ENABLED`.

## 6. Başka bir araca geçiş

Sistem tek bir araca bağlı değildir: Python 3.12 + stdlib, SQLite, ffmpeg.
Devralan araç için yeterli olan: `docs/SISTEM-ANALIZI.md`,
`docs/DEPARTMAN-ANALIZI.md`, `docs/STUDIO.md`, `docs/AHOS-ENV.md`, testler ve
`quality/evidence/` altındaki JSON kanıtlar. Hiçbir adım bu dosyalarda
yazılı olmayan bir bilgiye dayanmaz.
