# OpenMontage entegrasyonu — envanter ve minimum değişiklik planı

Tarih: 2026-11-08 · Durum: **PARTIAL / render BLOCKED** · harcama 0 EUR

## 1. Envanter özeti

| Sistem | Dosya var | Çalışıyor | Kanıt |
|---|---|---|---|
| OpenMontage | Evet | **Kısmi** | 13 pipeline, 248 test, Remotion node_modules 199 paket (offline) |
| Remotion render | Evet | **HAYIR** | `--version` 90 sn yanıtsız; render denenmedi |
| `workflows/` | Evet (8) | Doğrulanmadı | LTX2/ComfyUI JSON; GPU yok |
| `custom_nodes/ltx2_compat` | Evet (1) | Doğrulanmadı | ComfyUI kurulu değil |
| `studio/` | Evet | **SPEC_READY** | 16/16 kimlik, 0 onaylı görsel |
| `deliverables/` | Evet | Test varlığı | 5 sn take2 + keyframe |
| RunPod | Yapılandırılmış | **Ulaşılamıyor** | health 10 sn timeout; ücretli başlatma yok |
| Oracle | Evet | **SSH açık / Ollama kapalı** | 22 açık, 11434 kapalı |
| Model ağırlıkları | Sınırlı | Kısmi | HF: zeroscope + Kokoro; SDXL/Kontext yok |

## 2. Minimum değişiklik planı

**OpenMontage kodu değiştirilmeyecek.** Mevcut `pipeline_defs/character-animation.yaml` kullanılacak.

1. **Salt-okunur adaptör:** Karakter girdileri `studio/characters/<id>/` altından okunur; kopya üretilmez.
2. **Bütçe override:** Pipeline'ın `budget_default_usd: 2.00` değeri **0.00** ve onay kapılı çalıştırılır.
3. **Açılış props:** `studio/integration/openmontage-props/s01e001-opening-storyboard.json` — 6 text-card, 30 sn; karakter görseli yok.
4. **Render:** Remotion CLI düzelirse `Explainer` kompozisyonu ile 30 sn storyboard animatiği denenir; başarısızsa video üretilmiş sayılmaz.
5. **Lisans:** AGPLv3 ticari kullanım incelemesi tamamlanmadan yayın/dağıtım yok.

## 3. Karakter bağlantısı

`openmontage-bridge.json` 16 karakteri şu alanlarla eşler: `canon_dir`, `visual_status`, `voice_status`, `owner_approval`.
- Görsel: yalnız Aden/Kaan `NEEDS_REVISION`; 14 karakter `MISSING`.
- Ses: 14 `READY_FOR_QA`, 2 bebek `MISSING`.
- **Onay: 0/16** — hiçbir karakter OpenMontage üretimine "approved" olarak giremez.

## 4. İlk doğrulanabilir çıktı

**Aday:** 30 sn `EPISODE-OPEN-30s` text-card storyboard animatiği.
**Durum:** `PROPS_READY_RENDER_BLOCKED` — props şeması hazır (6 cut / 30 sn), render CLI yanıtsız.
**Video:** yok. Bu nedenle "ilk üretim çıktısı" olarak video raporlanmadı.

## 5. Maliyet koruması

- Canlı LLM noktası: `llm_executor.http_transport` → `_studio_budget_preflight` (12.000 token, 0 USD).
- OpenMontage CostTracker: 10 USD toplam, 0.50 USD tek işlem onayı, `cap/warn`.
- Eksik: görev önbelleği ve pending>300 kontrolü OpenMontage/AHOS yürütücüsüne bağlı değil.
- Ücretli RunPod/Oracle kaynağı **başlatılmadı**.

## 6. Engeller

1. Remotion CLI yanıtsız → gerçek video yok.
2. 14 karakterde görsel kanon yok.
3. 0/16 sahip onayı.
4. AGPLv3 ticari lisans incelemesi.
5. RunPod erişilemiyor; Oracle Ollama kapalı.
