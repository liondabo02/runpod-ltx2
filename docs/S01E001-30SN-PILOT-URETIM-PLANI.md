# AHOS Çizgi Film Stüdyosu — S01E001 / 30 saniyelik pilot taslağı

**Durum:** PROPOSED / **sahip onayı yok**, GPU üretimi yok, ücret yok.
**Makine-okunur shot list:** `workflows/S01E001-pilot-30s-plan.json`
**Okunabilir üretim kapısı:** `python tools/studio_pilot_preflight.py`

## Neden hazırlandı?
Bu çalışma 8 dakikalık **"Uçurtmanın Kayıp Kuyruğu"** bölümüne aday olan, yalnız Aden ve Kaan'ı kullanan **30 saniyelik ön izleme planıdır**. Eski `S01E001/story-packet.local.json` yalnız "sharing and teamwork" başlıklı genel bir taslaktır, `owner_approved: false` durumundadır. Bu pilot onu silmez, onaylanmış sekiz dakikalık senaryo olarak temsil etmez.

## 3 sahne / 6 çekim / 30 saniye
| Süre | Bölüm | Kamera | Eylem / replik | Ses |
|---|---|---|---|---|
| 00–05 | Açılış | Çocuk göz hizasında sabit geniş | Aden (3, kız) ve Kaan (1, erkek), uçurtmayı inceler | Park ambiyansı |
| 05–10 | Sorun | Aynı yön ve sabit kadraj | Kuyruk yakına düşer. Aden: "Aa! Uçurtmanın kuyruğu!" | Hafif rüzgâr/kumaş |
| 10–15 | Arayış | Sabit orta | Aden: "Bir bakalım... Nerede?" Kaan kısa "Aa!" der | Merak müzik motifi |
| 15–20 | Bulma | Yerdeki kurdele kadrajda | Aden: "İşte burada!" Kaan el çırpar | Kısa sıcak vurgu |
| 20–25 | Çözüm | Sabit orta | Aden yere konmuş uçurtmanın geniş cırt cırtını takar | Kumaş/cırt |
| 25–30 | Final | İki çocuk kadrajda | Uçurtma yükselir. Aden: "Birlikte başardık!" Kaan: "Ya!" | Neşeli kapanış |

**Teknik gerekçe:** Her klip en çok 5 saniye; mevcut ücretsiz I2V hattının yaklaşık 5 saniyelik çıktı sınırına uygun. Dışa aktarılan 1080p, gerçek yerel 1080p üretilmediği sürece `upscale` olarak etiketlenecek.

## Kimlik ve güvenlik kilidi
- Aden **kız**, tek sarı yıldız toka, omuz hizasında saç, sol yanağın görünen açılarında üç çil; kobalt mavi üst.
- Kaan **1 yaş erkek**, bebeksi oranlar, kısa siyah kıvırcık saç, mercan kırmızı üst. Yalnız kısa heceler; yetişkin gibi uzun diyalog yok.
- İkili aynı boyut sırasını ve yüz/saç/kıyafet referanslarını korur. 98 cm / 76 cm kanon oranı.
- Kaan'ın boynuna, eline, ayağına uçurtma ipi dolanmamalı; bebek makarayı taşımamalı. Kadrajda yetişkin eklemek yerine güvenli gözetim dış kadrajdan varsayılabilir.
- Park, ışık yönü ve dört renkli uçurtma paleti mevcut `characters/scenes/park-kite-01.json` ile korunmalı.
- Ek çocuk, uydurma ebeveyn, ikinci uçurtma ve istemsiz logo yok.

## Kalite kapıları
1. **Plan QA:** Üç sahne, altı çekim, toplam 30 saniye; izinli karakterler ve çocuk konuşma sınırı. `tools/studio_pilot_preflight.py`.
2. **Görsel QA:** Aden turnaround/ifadeler, Kaan turnaround/ifadeler **v2** dosyaları manifest SHA-256 ile doğrulanmalı. v1'i v2 diye göstermek yasak.
3. **İnsan onayı:** `pilot-owner-approval.local.json` özel kaydı olmadan checker `render_allowed=false` verir. İnsan onayı olmadan `--all` ile görsel kilit atlanmaz.
4. **Teknik QA:** Gerçek MP4, ölçülen FPS/süre, freeze ve flicker. Yaratıcı kaliteyi teknik PASS ile eşitleme.
5. **Yaratıcı QA:** 3 yaş kız / 1 yaş erkek, aynı yüz ve kıyafet, iki çocuk kadrajda, ışık/prop sürekliliği, doğal eylem, anlaşılır diyalog, eğitim hedefi. Son karar sahibi verir.

## Bu turda doğrulanmayan / yapılmayan
- Nihai v2 model sheet'leri henüz üretilmedi; ücretsiz ZeroGPU kotası dolu.
- Önceki 5 saniyelik take2 dosyası gerçek çıktı; bu **30 saniyelik yeni pilot değildir**.
- Üç sahnelik plan bir **çekim ve seslendirme taslağıdır**; yeni MP4 veya onaylı 8 dakikalık bölüm değildir.
- Gerçek 3D mesh/rig, stüdyo seviyesinde hareket ve kanonik ses kalite onayı henüz yok.
- Ücretli servis, yeni hesap/anahtar ve sahne renderı çalıştırılmadı.

## Sonraki tek doğru adım
Aden turnaround v2 ücretsiz kota açıldığında üretilecek, kalite incelemesine sunulacak; **sahip onayı olmadan** diğer v2 sayfalar ve 30 saniyelik klipler üretilmeyecek. Bu planda sessizce yeni karar onayı verilmez.
