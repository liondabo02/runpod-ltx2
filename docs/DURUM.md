# Sistem durumu — 6 Kasım 2026, 20:05

## Canlı

| Bileşen | Durum |
|---|---|
| Daemon | pid 33176 · running · tur artıyor · `daemon-state.json` güncel |
| Zamanlayıcı | `AHOS-Cadence` · günlük 07:00 · 02–06 Kasım raporları yazıldı |
| Model tüneli | açık (qwen2.5-coder:3b, 7b) |
| Kuyruk | 3.961 completed · 145 pending · 43 blocked · 13 failed |
| Departman | 17/17 teslim edebilir (hukuk dahil) |
| Test | 1.207 passed · 36 skipped · **kapsam %76** |
| Harcama | 0,278 $ (toplam) |

## Bu turda düzeltilen üç arıza

1. **Daemon döngüsü kaybolmuş** — `daemon.py` tek tur atıp çıkıyordu, launcher ise
   uzun ömürlü süreç bekliyordu. Döngü, bayrak ayrıştırma ve durum dosyası geri
   getirildi (`686f39a`).
2. **cp1252 çökmesi** — Türkçe durum metni yazdırılırken `UnicodeEncodeError`
   alıyordu; stdout/stderr UTF-8'e çevrildi.
3. **Saatlik kota hatası** — iki alt hata: `updated_at` biçim karışıklığı ve
   "son 60 dakika" penceresi. Artık takvim saati bazlı sayılıyor (`883b279`,
   `b1b902e`).

## Kuyruk triyajı

```
önce  : 967 pending (821'i yinelenen "kriz görevi")
sonra : 145 pending (821 + 11 bayat iptal, kanıt silinmedi)
```

Kök neden: eski daemon imajı, kriz görevi tekrarını engelleyen düzeltmeden önce
başlatılmıştı. Güncel kod tekrar üretmiyor (ölçüldü: `missions: []`).

## Kapsam

`coverage` 7.17.2 · %76 (23.147 ifade, 5.648 kaçan) · eşik `fail_under=70` ·
CI'da ayrı ubuntu adımı. Ayrıntı: `docs/KAPSAM.md`.

## Kalan açıklar

1. **Kod modeli** — hâlâ yerel 7b; `software`/`oyun` kod görevleri engelleniyor.
   Ücretsiz çözüm hazır ama **`NVIDIA_NIM_API_KEY`** gerekiyor.
2. **RunPod kredisi** — sinematik video katmanı kapalı.
3. **CI görünürlüğü** — GitHub token'ı yok; iş akışı sonucu buradan görülemiyor.

## Not: eşzamanlı çalışma

Aynı ağaçta başka bir ajan da commit atıyor (`a0f22be`, `a6067f3`, `4937b44`…).
Çakışmayı önlemek için yalnız kendi dosyalarımı stage ettim; `git reset` veya
toplu `git add -A` kullanılmadı.
