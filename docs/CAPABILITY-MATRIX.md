# AHOS Studio — Capability Matrix (Faz 1)

_Ölçüm: 2026-11-15 · Dal `feature/studio-professional-skills` · HEAD `f94c443` · Ağaç temiz_

## Ortam (gerçek ölçüm)
```
ffmpeg = VAR   ffprobe = VAR   blender(PATH) = -   blender-4.5.16 dizini = VAR
godot = -   rhubarb = -   piper = -   espeak = -
python: edge_tts=N numpy=N PIL=N cv2=N   piper=-  whisper=-
disk boş = 35 GB     GPU (nvidia-smi) = YOK
```

## Matrix
| Yetenek | Aday | Kaynak | Sürüm/Lisans | Donanım | Ücret/Anahtar | Risk / Geri alma | Karar |
|---|---|---|---|---|---|---|---|
| 3D model + rig + render | **Blender 4.5.16** | blender.org | 4.5 LTS · GPL-3.0 (OSI, ticari kullanım açık) | CPU yeterli; GPU opsiyonel | Ücretsiz, anahtar yok | Kurulu dizin: `C:\\actions-runner\\_work\\blender-4.5.16-windows-x64`; geri alma = dizini kullanmamak | **INSTALL (mevcut, PATH'e eklenmeli)** |
| 2D iskelet rig + animasyon | Godot 4.x | godotengine.org | 4.x · MIT (OSI) | CPU | Ücretsiz | ~120 MB indirme; geri alma = dizin sil | **EVALUATE** (indirme onayı) |
| Lip-sync (viseme) | Rhubarb Lip Sync | github.com/DanielSWolf/rhubarb-lip-sync | MIT olduğu **doğrulanmalı** (resmî LICENSE) | CPU | Ücretsiz | ~10 MB; geri alma = sil | **EVALUATE (lisans doğrulanacak)** |
| Fonem/forced alignment | Whisper (openai/whisper) | github.com/openai/whisper | MIT (kod); **model ağırlıkları ayrı lisans** | CPU (yavaş) / GPU | Ücretsiz | small ≈ 460 MB, medium ≈ 1.5 GB → **500 MB kuralı** | **BLOCKED_SIZE** (onay gerekir; small sınırda) |
| TR TTS (kadın/erkek) | edge-tts | pypi | MIT (kod) · Microsoft servis ToS | CPU | Ücretsiz, anahtar yok | Kurulu (`edge_tts=VAR`) | **INSTALL (mevcut)** |
| TR TTS (yerel, çocuk sesi) | Piper | github.com/rhasspy/piper | Kod MIT; **ses modelleri ayrı lisans** | CPU | Ücretsiz | Model ~60-100 MB/ses; geri alma = model sil | **EVALUATE** (model lisansı ses bazında doğrulanacak) |
| Video üretimi (AI) | ComfyUI + LTX/Wan | comfyanonymous/ComfyUI · Lightricks/LTX-Video | GPL-3.0 (ComfyUI) · model lisansları ayrı | **NVIDIA GPU + ≥16-24 GB VRAM** | Model indirmesi çok GB | GPU yok; ayrıca >500 MB | **BLOCKED_GPU / BLOCKED_SIZE** |
| Müzik | Repo içi prosedürel (`music_bed`) | bu repo | kendi kodumuz | CPU | Ücretsiz | Yok | **INSTALL (mevcut)** |
| QA (süre/motion/ses/kontur) | Repo içi (`verify_production`) | bu repo | kendi kodumuz | CPU | Ücretsiz | Yok | **INSTALL (mevcut)** |
| Longform planlama | Repo içi (`series`, `studio_department`) | bu repo | kendi kodumuz | CPU | Ücretsiz | Yok | **INSTALL (mevcut)** |
| Süreç becerileri | ECC benzeri skill paketleri | — | Toplu kurulum **yasak** | — | — | Tek tek inceleme gerekir | **EVALUATE (max 3, MIT/Apache, hooksuz)** |

## Notlar
- **Kod çizimi (PIL) estetik amaçla kullanılmayacak**; kalite motor/asset işidir.
- Bu makinede **GPU yok** → AI video ailesi tümüyle `BLOCKED_GPU`.
- 500 MB üzeri indirme kuralı: Whisper medium+, LTX/Wan modelleri → **onay istenmeden indirilmeyecek**.
- Ticari kullanım: Blender GPL ve Godot MIT temiz; **edge-tts Microsoft servis ToS** ve **Piper ses modelleri** ayrıca doğrulanmalı (BLOCKED_LICENSE riski burada).

## Faz 2 için önerilen ilk kurulum (onay bekliyor)
1. **Blender’ı PATH’e ekle** (indirme yok, kurulu) → rig/animasyon doğrulaması: `blender --version` + tek kare render.
2. **Piper TR ses modeli** (~60-100 MB) → lisansı ses bazında kontrol edilip kurulacak.
3. **Rhubarb** (~10 MB) → LICENSE dosyası okunup MIT ise kurulacak.
