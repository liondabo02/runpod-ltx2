# RENDER v2 — Sanat Spesifikasyonu (Cartoon Network tarzı)

Amaç: `studio_2d` çizimini "düz vektör iskelet"ten **CN tarzı, belirgin karakterli**
çizgi filme çıkarmak. Tamamı kodla, **0 €**, GPU yok. Her kural ölçülebilir.

## 1) Çizgi ve renk (kimlik)
- **Kontur:** her karakter/prop için dış hat **6–8 px @1080p** (720p çizimde 4–5 px),
  renk `#1A1A1F` (saf siyah değil). İç detay çizgisi 2–3 px.
- **Palet:** 1 ana + 1 gölge + 1 vurgu / karakter. Gölge = ana renk %18 koyu,
  vurgu = %22 açık. **Gradyan yok** (CN düz renk mantığı).
- **Arka plan:** karakterden **daha açık, daha az doygun** (kontrast hiyerarşisi):
  zemin/duvar düz renk + 1 katman prop; karakter asla arka planla aynı değerde değil.

## 2) Oranlar (belirgin karakter)
- **Kafa** = toplam boyun **1/3'ü** (çocuk karakterde 1/2.6). Gözler kafa genişliğinin
  **%38'i** (iri ifade), göz bebeği kafa genişliğinin %22'si.
- **Silüet testi:** karakter siyah doldurulduğunda **tek bakışta tanınmalı**:
  saç şekli, kıyafet kesimi ve duruş birbirinden farklı olmalı.
- **El/ayak** abartılı (ayak = kafa genişliğinin %55'i), parmak çizilmez (CN stili).

## 3) Animasyon (canlılık)
- **Snap timing:** jestler 2 karede başlar, 3 karede oturur (24 fps) — yumuşak değil.
- **Anticipation:** her hareket öncesi 2 kare ters yön (CN'in imzası).
- **Blink:** 4–6 sn'de bir, 2 kare. **Ağız:** konuşurken 3 kademeli açıklık
  (kapalı/yarım/tam) — sürekli sinüs dalgası değil.
- **Bacak/kol:** yürüyüşte 8 karelik döngü; konuşurken sabit ayak, üst gövde hareketli.

## 4) Kamera ve kurgu
- **Sahne içi:** 3 çekim ölçeği dönüşümlü — geniş (kuruluş) → orta (diyalog) →
  yakın (duygu). Her çekim **min 2 sn**, max 6 sn.
- **Hareket:** `slow_pan` (0.35 rad/s), `punch_in` (%1.02 → %1.06), `shake` (vuruşta
  2 kare, ±3 px). Yeşil/sert kesme yerine **1 kare beyaz flash** (CN geçişi).
- **Geçiş:** sahne arası 4 kare `dip-to-color` (sahne paletinin vurgu rengi).

## 5) Tipografi / altyazı
- Altyazı: kalın, **konturlu** (2 px) beyaz yazı + karakter rengi şerit; alt %14'te.
- Konuşan karakterin adı **renk kodlu** (karakter paletinden).
- Bölüm başlığı: 2.5 sn, 96 px, hafif eğimli (CN başlık kartı), gölge offset 4 px.

## 6) Ses/hareket eşleşmesi (mevcut altyapı)
- `amplitude_envelope` → ağız 3 kademe; vurgu (RMS tepe) anında `shake` + jest.
- Müzik: sahne başına tempo değişimi (84→104 bpm aksiyonda), geçişte 1 vuruş sus.

## 7) Kabul kriterleri (test edilebilir)
1. `verify_production`: `motion_ok` (skor ≥ eşik), `cuts_ok`, `duration ±0.5 sn`, `audio_ok`.
2. **Silüet testi:** iki karakterin siyah silueti %15'ten az örtüşür (piksel oranı).
3. **Kontrast testi:** karakter bölgesi ile arka plan arası ΔL ≥ 25 (0-255).
4. **Kontur testi:** karakter sınırında `#1A1A1F` piksel oranı ≥ %70 (kenar örneklemi).
5. **Statiklik yasağı:** ardışık karelerde piksel farkı 0 olan çekim sayısı = 0.

## 8) Uygulama sırası (her adım: test → commit → kanıt)
1. `_character`: kontur + gölge/vurgu paleti + oranlar + iri göz + abartılı el/ayak.
2. Silüet/kontrast/kontur testleri (`tests/test_studio_2d.py`).
3. Snap timing + anticipation + 3 kademeli ağız.
4. Paralaks arka plan katmanları + zemin gölgesi.
5. `punch_in` / `shake` / `dip-to-color` geçişleri.
6. Tipografi (konturlu altyazı, renk kodlu isim, CN başlık kartı).
7. SFX: adım/vurgu/vuruş (ffmpeg ile üretilen kısa örnekler, 0 €).
8. `verify_production`'a silüet/kontrast/kontur kontrollerini ekle (fail-closed).

> Not: Bu spesifikasyon "mükemmel" iddiası değil; **CN tarzına yaklaşan, ölçülebilir**
> bir çıtadır. Her madde kod + test ile doğrulanmadan "bitti" sayılmaz.
