# S01E001 v2 — yaratıcı revizyon ve üretim hazırlığı

Durum: **DRAFT_FOR_OWNER_APPROVAL** · v1 korunur · görsel/ses üretimi yok

## 1. QA bulguları → v2 çözümleri

| QA bulgusu | v2 çözümü |
|---|---|
| P0: İki "30 sn pilot" aynı adla anılıyor | `POC-30s` ve `EPISODE-OPEN-30s` ayrı dosya/dil; `POC-30S-NOTU.md` |
| P0: Açılışta kuyruk bağlanırken ana senaryoda S02'de bağlanıyor | Tek kronoloji: S01 beat 1–3 açılışın tamamı; bağlama S01'de başlar, S02'de biter |
| P1: İlk sorun 2:02'de | Kuyruk **S04'te 2:10'da** kopuyor; ilk 30 sn'de gıdıklama/komik şapka, 45 sn'de hedef, 1:30'da ilk uçuş |
| P1: 480 sn'de 66 kelime, durağan sahneler | **58 somut beat**, her biri 5–10 sn; 34 replik; sessiz görsel mizah ve mikro-vuruşlar |
| P1: Park→ev→park, ışık/gün batımı tutarsızlığı | **Tek mekân: park**; 11 sahne, kumaş çantası piknik örtüsüne gelir; sabah ışığı sabit |
| P1: Kaan'ın küçük şerit/ip tutması | Kaan yalnız bakar, işaret eder, güler, büyük şeridi iter; ip yetişkin gözetiminde |
| P1: Harun yalnız kapanışta, akrabalık doğrulanmamış | Kanon doğrulandı: **uncle_of (dayı)**; QA gereği ilk bölümden çıkarıldı, sonraki bölüme bırakıldı |
| P1: Esra'nın görsel kanonu yok | Açılışta Esra **kadraj dışı ses**; ilk kalite pilotu iki karakterli |
| P2: "Paylaştınız, yardım ettiniz" sloganı | Kapanış davranışla: kurabiye paylaşımı, kuyruğun dansı; ders cümlesi yok |
| P2: Kaan'ın kelime dağarcığı geniş | **Dört kısa ses:** "Kuş!", "Aa!", "Mavi!", "Ya!" |

## 2. Prodüksiyon sadeleştirmesi

| | v1 | v2 |
|---|---|---|
| Sahne | 12 | **11** |
| Mekân | Park + ev | **Yalnız park** |
| Geçiş | Park→ev→park | **Yok** (tek mekân) |
| Işık | Sabah → gün batımı | **Sabah, sabit yön** |
| Beat | Yok | **58 beat, 5–10 sn** |

## 3. Açılış kancası (ilk 20 sn)

1. 0–10: Rüzgâr kuyruğu canlandırır, Kaan'ın yanağını gıdıklar.
2. 10–20: Kuyruk Kaan'ın başına renkli peruk gibi düşer; "Aa!" ve gülüş.
3. 20–30: Esra (ses) yönlendirir; Kaan mavi panele dokunur; Aden düğüme başlar.

İlk 30 sn'de somut hedef: **piknikten önce uçurtmayı uçurmak**.

## 4. Ses haritası

- 34 replik; her biri karakter + duygu + konuşma süresi + zaman kodu (`SES-HARITASI-v2.md`).
- **Ses üretilmedi**; mevcut 24 kHz referanslar yalnız ses izi.
- Kaan dört kısa ses; çocuk doğallığı insan dinlemesiyle doğrulanmadan onay yok.

## 5. Harun kararı

- Kanon: `harun-uncle_of-aden`, `harun-uncle_of-kaan` → **dayı**.
- İlk bölümde anlamlı tanıtım için yer yok; QA P1 gereği çıkarıldı.
- Sonraki bölümde erken tanıtım + görsel kanon ile geri gelecek.

## 6. Kapılar

1. **Sahip onayı** yok → final değil.
2. **Görsel v2 yok**; ZeroGPU kotası kapalı (son kontrol 00:15). Ücret yok.
3. Kota açılınca yalnız **Aden turnaround v2**; onay olmadan diğer sayfalar yok.
4. Seslendirme/animatik, senaryo onayından sonra.

## 7. Doğrulama

- `tools/validate_s01e001_v2.py`: 480/30, 58 beat, kronoloji, açılış uyumu, Kaan sözlüğü, v1/POC koruması.
- `tests/test_s01e001_v2.py`: 7 test; v1 testleri ayrıca 6 test.
