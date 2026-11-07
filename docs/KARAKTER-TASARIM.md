# Aden & Kaan — profesyonel karakter tasarımı (v2 yolda)

Tarih: 2026-11-07 · Kanon: Aden 3 yaş **kız**, Kaan 1 yaş **erkek**
Durum: **v2 kararları kilitlendi; v2 görselleri kota nedeniyle BEKLİYOR.**

> Önemli: Bunlar **görsel referanstır (model sheet)**. Gerçek 3D mesh, rig veya
> oynatılabilir model **üretilmedi**; "3D model" olarak adlandırılmaz.

## 0. v2 kararları (Harun, şartlı onay)

| Karakter | Karar | Kanon dosyası |
|---|---|---|
| Aden | 3 yaş **kız**; omuz hizası saç; **TEK** sarı yıldız toka; **3 çil** tüm panellerde | `characters/aden.json` |
| Kaan | 1 yaş **erkek**; daha büyük kafa, kısa bacak, dolgun yanak, bebeksi gövde (**3,0 kafa**) | `characters/kaan.json` |

**v2 görsel durumu:** Aden turnaround/ifade retouch + Kaan bebeksi retouch + Kaan
ifade sheet → **ZeroGPU kotası 0** (`You have exceeded your free ZeroGPU quota`).
Ücret harcanmadı; onaylı ücretli yol veya kota sıfırlanması bekleniyor.
JSON kanonu değil, **gerçek görsel** teslim edilecek.

## 1. Üretilen görseller

| Karakter | Görsel | Durum |
|---|---|---|
| Aden | full-body referans (FLUX.1-schnell, seed 78) | hazır |
| Aden | 4 görünüş turu — ön / 3-4 / yan / arka (Kontext, seed 101) | hazır |
| Aden | 6 ifade — nötr, mutlu, şaşkın, üzgün, korku, merak (Kontext, seed 202) | hazır |
| Kaan | full-body referans (FLUX.1-schnell, seed 80) | hazır |
| Kaan | 4 görünüş turu (Kontext, seed 303) | hazır |
| Kaan | 6 ifade | **PENDING — kota** |

Etiketli sayfalar: `ADEN-turnaround-labeled-v1.png`, `ADEN-expressions-labeled-v1.png`,
`KAAN-turnaround-labeled-v1.png`, `KAAN-expressions-PENDING-v1.png`.

Konum (private, git dışı):
`control_plane_v2/runtime/private/animation-studio/model-sheets/`
Manifest: `model-sheets-manifest.local.json` (model, space, seed, SHA-256, tarih).

## 2. Kaynak model ve sürüm kaydı

| Üretim | Model/Space | Seed | Çıktı |
|---|---|---|---|
| Aden referans | `black-forest-labs/FLUX.1-schnell` | 78 | 768×1024 |
| Aden tur | `black-forest-labs/FLUX.1-Kontext-Dev` | 101 | 880×1168 |
| Aden ifade | `black-forest-labs/FLUX.1-Kontext-Dev` | 202 | 880×1168 |
| Kaan referans | `black-forest-labs/FLUX.1-schnell` | 80 | 768×1024 |
| Kaan tur | `black-forest-labs/FLUX.1-Kontext-Dev` | 303 | 880×1168 |

Promptlar manifestte ve `characters/*.json` kanonunda; her görselin SHA-256'sı
manifestte. Ücret: **0 USD** (ücretsiz ZeroGPU kotası; token değeri loglanmadı).

## 3. Tutarlılık değerlendirmesi (dürüst)

**Tutan:** yüz tipi, göz rengi/büyüklüğü, saç rengi ve kesimi, tişört/short/ayakkabı
renkleri, 3 yaş / 1 yaş oranları, dört görünüşte aynı karakter.

**Tutmayan / not edilen:**
- Aden'in **3 çili** bazı panellerde görünmüyor; kanonda kalabilmesi için retouch gerekir.
- Saç tokası: kanon "bir sarı yıldız toka"; görselde **üç yıldız** çıktı, tüm görünüşlerde
  tutarlı. Karar sizin: kanonu 3 yıldıza çekmek veya tek yıldıza retouch.
- Kaan referansında kollar göğüste (A-pose değil); turnda düzeltildi.
- Kaan ifade sheet'i **üretilmedi** (kota); placeholder sayfa açıkça "PENDING" yazıyor.
- Kaan 1 yaş için hafif büyük görünüyor (1,5–2 yaş okuması); oran 3,1 kafa.

## 4. Kalite çıtası

Üst düzey stüdyo çıtasına göre: **karakter çekiciliği ve görünüş tutarlılığı umut verici**,
ancak bu bir **konsept/model sheet** seviyesidir. Profesyonel üretim için:
retopoloji + rig + blend-shape ifadeler + doku (PBR) gerekir; bunlar yapılmadı ve
"3D model" denmedi. Görseller insan incelemesine sunulmuştur.

## 5. Onay kapısı

Harun Aden ve Kaan tasarımını onaylamadan:
- 14 karakterin toplu görsel üretimi **başlamaz**,
- yeni video varyasyonu **üretilmez**.

Onay sonrası sıra: Kaan ifade sheet (kota/onay) → 14 karakter model sheet →
3 sahnelik pilot.

## 6. Test ve ortam

Kanonik ortam: `control_plane_v2/.venv` (Python 3.12.7). `cv2` ve `gradio_client`
bu ortama kuruldu; aynı 14 test venv'te de geçiyor (`docs/ORTAM.md`).

`conflicts=16` artık kategorilidir:
`missing_visual_canon=14` (bilgi), `baby_audio_absent=2` (bilgi: Medine/Ramin),
`technical_identity_conflict=0` (hata).
