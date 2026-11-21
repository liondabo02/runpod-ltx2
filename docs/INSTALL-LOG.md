# AHOS Studio — Install Log (Faz 2)

Tarih: 2026-11-16 · Repo: `C:\actions-runner\_work\AHOS-work-s1`
Kural: ücretsiz, lisansı doğrulanmış, repo dışı kurulum; ücretli/GPU yok.

## Blender 4.5.16 LTS

- Kaynak: https://www.blender.org/download/lts/
- Lisans: GPL-3.0 (OSI; ticari kullanım açık)
- Konum: `C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe`
- Shim: `tools\blender.cmd` (env: `AHOS_BLENDER_EXE`)
- Doğrulama:

```powershell
cmd /c "tools\blender.cmd -b -noaudio --factory-startup --python tools\blender_smoke.py"
# BLENDER_SHIM_OK · Blender 4.5.16 LTS · exit 0
```

## Rhubarb Lip Sync 1.14.0

- Kaynak: https://github.com/DanielSWolf/rhubarb-lip-sync/releases/tag/v1.14.0
- Lisans: **MIT** (resmî LICENSE; ticari kullanım açık)
- Zip SHA-256: `62FA416A8D5E382A3828EE4BEF358CE520D0B4CABDEAEA75A7AC266D098D1FE3`
- `rhubarb.exe` SHA-256: `9E289C6B5939EF6B306A61E8105EC721FD8D52B3CE950D08891EA3CC7DF5718D`
- Kurulum: `C:\actions-runner\_work\tools\rhubarb\Rhubarb-Lip-Sync-1.14.0-Windows\`
- Shim: `tools\rhubarb.cmd` (env: `AHOS_RHUBARB_EXE`)
- Doğrulama:

```text
rhubarb.exe --help → exit 0
Gerçek Türkçe WAV (edge-tts geçici ses, 3.55 sn)
rhubarb -f json -o mouth.json --machineReadable lipsync-test.wav
→ 10 mouthCue, süre 3.55 sn, exit 0
```

Adaptör: `ahos_core/ahos/lipsync.py`
Test: `python -m pytest tests/test_lipsync.py -q` → **5 passed**.

## Kurulmayanlar

| Araç | Karar | Neden |
|---|---|---|
| Godot 4 | EVALUATE | 120 MB; 2D rig kararı bekliyor |
| Piper TR | BLOCKED_LICENSE | Ses modeli lisansı ses bazında doğrulanmadı |
| Whisper | BLOCKED_SIZE | small ≈460 MB; Rhubarb viseme için yeterli |
| ComfyUI/LTX/Wan | BLOCKED_GPU | NVIDIA CUDA/VRAM yok |

## Ücret / güvenlik

- Yeni harcama: **0 EUR**
- API anahtarı koda/ rapora yazılmadı; edge-tts geçici ses olarak etiketli.
- Kalite eşikleri düşürülmedi; viseme yoksa adaptör hata verir, sahte cue üretmez.

## Godot 4.3.stable.official.77dcf97d8 · 2026-11-21T10:17:31
komut : C:\actions-runner\_work\tools\godot\Godot_v4.3-stable_win64.exe --headless --version
cikti  : 4.3.stable.official.77dcf97d8
lisans : MIT (godotengine.org/license)
konum : C:\actions-runner\_work\tools\godot\Godot_v4.3-stable_win64.exe
wrapper: tools\godot.cmd
