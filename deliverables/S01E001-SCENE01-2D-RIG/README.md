# S01E001 — İlk sahne, 2D iskelet teknik testi (v2)

**Durum:** `TECHNICAL_TEST_PENDING_REVIEW` · **profesyonel kalite: HAYIR** · **3D değil** · sessiz

- Video: `S01E001-SCENE01-2D-RIG-1080p24.mp4`
- 1920×1080 · 24 fps · **288 kare** · **12,0 sn** · H.264 · 1.267.451 bayt
- SHA-256: `4c429506c222b7cb9a4ec9b1d9871448346731f873b79172ba0c1a91030b46f1`
- Yöntem: **PIL 2D vector puppet** — kalça/diz/ayak, omuz/dirsek/el, boyun/baş, gözler, ağız; FFmpeg encode.
- Sahne: Aden yürür (0–4), durur/el sallar (4–6), konuşma ağzı (6–9), uçurtmaya bakar (9–12); Kaan emekler (0–4), bakar/gülümser (4–12); yavaş kamera push-in.

## Dürüst sınırlar

- **3D mesh/rig yok.**
- Yüz, kabul edilen posterin **vektör yaklaşımı**; birebir kimlik onayı yok.
- **Ses yok**, gerçek fonem/viseme yok; ağız hareketi zamanlamaya bağlı.
- Profesyonel gate: **FAIL** (model sheet/rig/voice/lipsync kanıtı 0/16).
- Storyboard gate: PASS; identity lock: PASS.
- Lisans: **UNVERIFIED**.

## Kanıt

- `qa.json` — ffprobe, kare farkı, boş kare
- `evidence/frame-0000.png`, `frame-0144.png`, `frame-0287.png`
- `studio_production_gate.py --level storyboard` → exit 0
- `studio_production_gate.py --level professional` → exit 2
