# Remotion + Claude Code Agent Skills — araştırma ve entegrasyon tasarımı

Tarih: 2026-11-07 · Durum: **araştırıldı, entegre edilebilir; tek başına karakter
animasyonu üretmez.**

## 1. Resmî mimari (doğrulanmış)

Remotion, React ile programatik video üretir; kareleri tarayıcıda (Chromium) çizip
MP4'e render eder. Agent Skills, Claude Code/Codex/Cursor gibi kod ajanlarına
Remotion projesinde **doğru API ve kalıpları** öğreten `SKILL.md` paketleridir.

Resmî kurulum ([remotion.dev/docs/ai/skills](https://www.remotion.dev/docs/ai/skills)):

```bash
npx skills add remotion-dev/skills
# veya
gh skill install remotion-dev/skills
```

Skill listesi (resmî): `remotion-best-practices`, `remotion-create`,
`remotion-markup`, `remotion-studio`, `remotion-render`, `remotion-maps`,
`remotion-captions`, `remotion-saas`, `remotion-interactivity`,
`remotion-docs`, `remotion-license`, `remotion-upgrade`, `remotion-multimedia`.

Kaynak: [github.com/remotion-dev/remotion/tree/main/packages/skills](https://github.com/remotion-dev/remotion/tree/main/packages/skills).

Bu makinede Node/npm/npx var; pnpm/bun yok. `npx` ile kurulum mümkün.

## 2. Ne yapar, ne yapmaz

| Yapar | Yapmaz |
|---|---|
| Hazır görselleri/katmanları sinematik kurguyla hareket ettirir (2.5D parallax, kamera) | Karakterin doğal yürüyüşünü/koşmasını **üretmez** |
| Başlık, altyazı, geçiş, renk düzeltme, overlay, montaj | Yüz ifadesi, kas/bez simülasyonu, ışık-gölge fiziği üretmez |
| Previz/animatik, shot list, süre ve ritim denemesi | Yeni bir karakter tasarlamaz (elindeki asset'i kullanır) |
| Tek komutla deterministik MP4 render | Model çıktısındaki bozulmaları (eriyen el/yüz) düzeltmez |

**Sonuç:** Remotion, LTX-2.5 gibi bir video modelinin **yerine geçmez**; onun
çıktısını kesmek, previz'ini almak ve teslim paketini hazırlamak için kullanılır.

## 3. Bu projeye entegrasyon tasarımı

```text
characters/*.json  ──►  keyframe prompt (image model)  ──►  I2V (LTX-2.5)
                                                     │
                                                     ├─► ham take.mp4
                                                     ▼
remotion/ (React)  ──►  previz / kamera / altyazı / renk / logo / süre kalibrasyonu
                                                     │
                                                     ▼
                                tools/creative_qa.py  ──►  teknik rapor
                                                     │
                                                     ▼
                                       Harun onayı (yaratıcı QA)
```

Kurulacak iskelet (henüz kurulmadı; anahtar/onay bekliyor):

```text
remotion/
  package.json            # remotion, @remotion/cli
  remotion.config.ts
  src/index.ts            # registerRoot
  src/Root.tsx            # Composition: ParkKite (1080p, 24 fps, 6 sn)
  src/scenes/ParkKite.tsx # katmanlar: arka plan, karakterler, uçurtma, ışık
  public/                 # assets/reference'tan kopyalanır (git'e girmez)
```

Render komutu:

```bash
npx remotion render ParkKite out/park-kite-previz.mp4 --fps=24 --crf=16
```

`remotion-docs` skill'i güncel API'yi çekmek için, `remotion-license` ise ticari
lisans şartını doğrulamak için kullanılır.

## 4. Lisans notu (kullanmadan önce doğrulanmalı)

Remotion'un ticari lisans şartı şirket büyüklüğüne göre değişir; resmî
`/remotion-license` skill'i ile doğrulanmadan üretimde kullanılmamalıdır.
Bu raporda "ücretsiz" denmedi.

## 5. Karar

- **Entegre edilebilir:** evet, previz + montaj + altyazı + teslim paketi için.
- **Tek başına sahne üretimi:** hayır. Profesyonel karakter animasyonu için
  LTX-2.5 (veya eşdeğeri) video modeli zorunlu.
- Bu yüzden ilk sahne için sıra: **LTX-2.5 I2V → Remotion son rötuş → QA**.
