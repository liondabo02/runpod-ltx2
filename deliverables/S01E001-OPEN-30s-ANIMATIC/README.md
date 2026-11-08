# S01E001 açılış animatiği — 30 sn

**Durum:** `VIDEO_READY` · **onay yok** · **sessiz** · karakter yüzü yok

- Video: `S01E001-OPEN-30s-ANIMATIC-1080p24.mp4`
- 1920×1080 · 24 fps · 720 kare · 30,000 sn · H.264 · 726.663 bayt
- SHA-256: `363b9043721cea776072a51c27c9d8f74a6ed7bb7c42cfa46e1887a4e107e566`
- Kaynak: `studio/integration/openmontage-props/s01e001-opening-storyboard.json` (6 kart / 30 sn)

## Üretim

1. OpenMontage Remotion 4.0.484 `Explainer` ile 900 kare (30 fps) render.
2. FFmpeg ile 24 fps'e dönüşüm; H.264 CRF 18, faststart.
3. Teknik QA: `qa.json` + `frames/` ilk-orta-son kareler.

## Sınırlar

- Ses yok; sessiz animatik.
- Aden/Kaan veya başka karakter görseli kullanılmadı.
- Her kart geçişinde 2 karelik spring fade (toplam 12/720) — siyah video değil.
- Onaylı bölüm veya ticari sürüm değil; lisans **UNVERIFIED**.
