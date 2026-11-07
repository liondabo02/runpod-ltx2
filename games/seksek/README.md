# Mipiluna · Seksek (tek oyun)

Mevcut `mipiluna/www/sokak-oyunlari.html` motorundan **Seksek** oyunu ayrıştırıldı;
tek oyunluk, kendi kendine yeten, mobil dokunmatik oynanabilir sürüm.

## Nasıl çalıştırılır?

```powershell
cd C:\actions-runner\_work\AHOS-GAME-SEKSEK
python -m http.server 8790 --bind 127.0.0.1 --directory games\seksek
```

Tarayıcı: **http://127.0.0.1:8790/**

Tek dosya olarak da açılabilir: `games/seksek/index.html` (ses dosyaları için HTTP önerilir).

## Oynanış

1. **Amaç:** taşı sırayla 1→8 karelere at, sonra ritim çubuğunda yeşil alanda dokunarak 8 kez zıpla.
2. Kareye tıklayınca taş fırlar; hedef kareye düşerse zıplama fazı başlar.
3. Yeşil alanda dokunmak `+denge`, ıskalamak dengeyi azaltır; denge 0 olursa oyun biter.
4. 8 zıplama tamamlanınca **+30 puan** ve 3 yıldız; **Başla** ile yeniden başlar.

## Özellikler

- Başlangıç ekranı (menü) + **Başla** düğmesi
- Puan, can, süre, denge çubuğu
- Oyun sonu ve **yeniden başlatma**
- Mobil dokunmatik (`pointerdown/move/up`), responsive tuval
- Öğretmen sesi/ipucu (mevcut mp3 dosyaları), ses kapatma
- `?auto=1` ile doğrudan oynanış (QA/test)
- `window.__qa` test kancası (start/finish/restart/snap)

## Kanıt

- Tarayıcı testi: `qa/browser-test.json` (Edge headless CDP, 0 hata)
- Ekran görüntüleri: `games/seksek/screenshots/` (menü, oynanış, bitiş, yeniden başlatma, mobil)
- Statik testler: `games/seksek/tests/test_seksek_static.py` (4 passed)
- Test betiği: `qa/cdp_test.py`
