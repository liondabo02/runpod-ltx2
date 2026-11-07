# S01E001 üretim hazırlığı — gerçek durum

Tarih: 2026-11-08 · Dal: `feature/ahos-s01e001-script` · Durum: **TASLAK, onay yok**

## 1. İncelenen mevcut paket

| Dosya | Ne | Durum |
|---|---|---|
| `control_plane_v2/runtime/private/animation-studio/episodes/S01E001/story-packet.local.json` | 5×96 sn jenerik "sharing and teamwork" taslağı; replikler şablon | **onaylı değil**, final sayılmaz |
| `.../production-graph.local.json` | 5 sahne, 10 shot, 480 sn iskelet | görsel üretim yok |
| `.../render-manifest.local.json` | render kayıtları | sahne renderı yok |
| `workflows/S01E001-pilot-30s-plan.json` | 3 sahne/6 klip/30 sn pilot | `PROPOSED_NOT_OWNER_APPROVED` |
| `docs/S01E001-30SN-PILOT-URETIM-PLANI.md` | pilot gerekçesi ve kapıları | onay yok |
| `deliverables/S01-PARK-KITE-001/` | 5 sn take2 kız versiyonu + keyframe | teknik test; 30 sn pilot değil |

Eski 34 sn pilot (erkek Aden) ve take1 **geçersiz**; referans olarak kullanılmaz.

## 2. Bu turda üretilenler

- `episode.json` — 12 sahne, **tam 480 sn**, 38 replik, üç davranış etiketi.
- `SENARYO-TR.md` — okunabilir Türkçe senaryo.
- `shotlist-30s.json` + `CEKIM-LISTESI-30SN.md` — ilk 30 sn, 6×5 sn, kamera/hareket/duygu/konum/ses/süreklilik.
- `voice-inventory.json` + `SES-ENVANTERI.md` — gerçek ölçüm (24 kHz mono, dBFS) ve eksik replikler.
- `tools/validate_s01e001.py` — süre/karakter/diyalog kapısı.
- `ahos_core/tests/test_s01e001_package.py` — 6 test.

## 3. Yeniden kullanılabilir öğeler

| Öğe | Yol | Kullanım |
|---|---|---|
| Park/uçurtma paleti ve ışık | `characters/scenes/park-kite-01.json` | ortam, renk, negatif prompt |
| Aden kanonu | `characters/aden.json` | yüz/saç/kyafet sürekliliği |
| Kaan kanonu | `characters/kaan.json` | bebeksi oran ve kıyafet |
| Kız Aden keyframe | `deliverables/S01-PARK-KITE-001/keyframes/keyframe-girl-seed-77.png` | görünüm referansı (model sheet değil) |
| 5 sn take2 | `deliverables/S01-PARK-KITE-001/park-kite-take2-girl-1080p.mp4` | hareket/ışık testi; bölüm değil |
| Pilot kamera/güvenlik | `workflows/S01E001-pilot-30s-plan.json` | çekim dili ve çocuk güvenliği |
| Ses referansları | `.../audio/core-voices/{aden,kaan,esra,harun}/tr.wav` | ses izi; replik değil |

**Kullanılmayacak:** eski erkek Aden görselleri, 34 sn reddedilen pilot, take1.
**Yok:** 3D mesh/rig, onaylı v2 model sheet, seslendirilmiş bölüm replikleri.

## 4. Kapılar ve engeller

1. **ZeroGPU kotası kapalı** (00:15 kontrolü: `zerogpu_quota`). Görsel üretim tekrarlanmadı; ücret harcanmadı.
2. Kota açılınca **yalnız Aden turnaround v2** üretilecek; kalite kapısı `awaiting_qc`; sahip görmeden diğer sayfalar yok.
3. **Ses onayı yok:** mevcut dosyalar 24 kHz mono jenerik referans; robotiklik/çocuk doğallığı dinlenmeden onaylanamaz.
4. **Sahip onayı yok:** senaryo ve çekim listesi `DRAFT_FOR_OWNER_APPROVAL`.

## 5. Sonraki doğru adımlar

1. Kota açılınca Aden turnaround v2 → kalite incelemesi → sahip onayı.
2. Onay sonrası Kaan v2 ve ifade sayfaları.
3. Seslendirme: 38 replik için gerçek çocuk/anne/dayı kaydı; robotik TTS'i final yapma.
4. 30 sn animatik: 6 çekim, mevcut 5 sn I2V hattı; native 1080p değilse upscale etiketi.
5. 8 dakikalık bölüm için sahne render planı; onaysız final kilidi yok.
