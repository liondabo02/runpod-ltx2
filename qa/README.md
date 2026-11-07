# QA kanıtları — Mipiluna Seksek

Ortam: Windows · Edge headless **Edg/156.0.4314.42** · CDP (port 9222)
Sunucu: `python -m http.server 8790 --directory games/seksek` → **http://127.0.0.1:8790/**

## Tarayıcı testi (gerçek oynanış)

```powershell
python qa/cdp_test.py
```

Adımlar ve ham sonuçlar (`qa/browser-test.json`):

| Adım | Sonuç |
|---|---|
| Menü yükleme | `document.title = "Mipiluna · Seksek"`, `__qa` mevcut |
| `__qa.start()` | `running=true`, score 0, can 3 |
| Tuval tıklaması (taş atışı) | hata yok, oyun çalışıyor |
| `__qa.finish()` | `running=false`, **score 30** |
| `__qa.restart()` | `running=true`, **score 0** |
| Konsol hataları | **0** |

```text
{"ok": true, "errors": 0}
```

Ekran görüntüleri: `games/seksek/screenshots/`
`01-menu.png` · `02-gameplay.png` · `03-finished.png` · `04-restarted.png` ·
`05-mobile-menu.png` · `06-mobile-gameplay.png` (390×844)

## Statik testler

```powershell
python -m pytest -q games/seksek/tests/test_seksek_static.py
4 passed
```

Kapsam: tek oyun (Seksek), başlangıç/puan/can/tuval, pointer olayları,
yeniden başlatma ve `?auto=1`, ses dosyalarının varlığı.

## Dürüst sınırlar

- Bu bir **2D tarayıcı mini oyunu**; 3D model/rig değil.
- Skor/oyun döngüsü tarayıcıda doğrulandı; insan eliyle uzun oturum testi
  (ör. 10 dakika) yapılmadı.
- Görsel stil Mipiluna'nın mevcut koyu tema paletini kullanır; yeni asset üretilmedi.
