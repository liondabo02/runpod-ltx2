# AHOS Çizgi Film Stüdyosu — 16 karakter hazırlık paketi

Durum: **SPEC_READY** · sahip onayı yok · harcama **0 EUR**

| Alan | Gerçek durum |
|---|---|
| Karakter kanonu | 16/16 READY |
| Görsel referans | 2/16 (Aden, Kaan) READY_FOR_QA; 14 MISSING |
| Ses referansı | 14/16 READY_FOR_QA; Medine/Ramin MISSING |
| 3D mesh / rig | 0/16 MISSING |
| S01E001 senaryo | v2, 480 sn, 55 beat (emirde 58 yazıyor — çelişki) |
| Storyboard | 55 çekim, board görseli yok |
| Video | yok; yalnız 5 sn teknik take2 |

## Dizinler

- `studio/canon/` — cast-manifest, family-relations, continuity-rules, style bibles
- `studio/characters/<id>/` — character, visual-dna, palette, motion, voice, model-spec
- `studio/production/` — readiness, asset-registry, work-orders, approvals, status
- `studio/s01e001/storyboard/` — shot-schedule + storyboard.md

## Engeller

- ZeroGPU kotası kapalı; ücretli yol yasak.
- Yerel CUDA/Blender/SDXL yok.
- 14 karakterde görsel kanon yok; model sheet üretilemez.
- **Kanıt:** `studio/production/cast-readiness.json`, `asset-registry.json`.
