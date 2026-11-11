# Aden 3D character library — v1 (technical model)

Durum: **TECHNICAL_MODEL_CREATED** · kimlik: **PENDING_IDENTITY_REVIEW** · rig: **NOT_STARTED**

Bu, onaylı Aden posterinden esinlenen, Blender'da **kodla üretilmiş özgün 3B geometridir**.
Sahip onaylı birebir benzerlik değildir; `IDENTITY_APPROVED` değildir.

## Model

- `aden-character-v1.blend` — 60 mesh objesi, 28.694 vertex, 29.935 face
- `aden-character-v1.glb` — glTF 2.0, aynı geometri
- `previews/` — ön, arka, sol, sağ, 3/4, yakın yüz (700×700)
- `model-stats.json`, `reopen-stats.json` — bağımsız Blender açılış doğrulaması
- `model-manifest.json` — kaynak SHA, model SHA, lisans/provenans, kimlik durumu

## Lisans / provenans

- Blender 4.5.16 LTS: GPL, ücretsiz; çıktı üzerinde hak iddia etmez.
- Geometri tamamen bu projede `build_aden_blender.py` ile üretildi; üçüncü taraf mesh/doku/model ağırlığı yok.
- Onaylı referans: `studio/reference/owner_accepted_roster_v1/characters/01_aden.png`
  SHA-256 `7c26afc668a9e9e352918ed618a1ae3b20da7b9e08e76a395a7e4c4ba2c14b7e`.
- FLUX.1-Kontext-Dev aday görselleri bu modelde kullanılmadı (non-commercial).
- Ticari kullanım: özgün geometri nedeniyle temiz; **kimlik onayı ayrı** ve henüz yok.

## Araç

- Blender 4.5.16 LTS portable:
  `https://download.blender.org/release/Blender4.5/blender-4.5.16-windows-x64.zip`
  SHA-256 `e258e90a1ebc14798ad65b3426bc5f11f5e0e013541c61cc7c3ee9bbf4ca0ce6`
- Yerel: `C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe`
- Donanım: ~15,3 GB RAM, AMD Radeon entegre GPU (512 MB), CPU Workbench render.
- Yeni harcama: **0 EUR**.

## Yeniden üretim

```powershell
& "C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe" -b -noaudio `
  --factory-startup --python tools/studio_backends/build_aden_blender.py `
  -- --out studio/assets/character-library/aden/v1

python tools/ahos_studio_dispatcher.py `
  --plan studio/jobs/p12b-character/plan.json `
  --job-dir studio/jobs/p12b-character --stage character_model
```

## Sınırlar

- Yüz benzerliği onaylı Aden'e yeterli değil; saç kümeleri stilize, gözler basit.
- Rig, skinning, mimik, yürüme ve konuşma yok.
- Profesyonel çocuk karakteri değil; P12-B teknik model kabulü için üretildi.
