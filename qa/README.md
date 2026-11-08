# Seksek QA — gerçek tarayıcı oynanışı

## Eski raporun sınırı

`qa/browser-test.json` ve `01-menu`–`06-mobile-gameplay` eski ilk denemeye
aittir. Eski testte **`__qa.finish()` ile puan verildiği için** gerçek kazanma
kanıtı değildir. Bunları tarihsel kayıt olarak koruyoruz; PASS dayanağı yapmıyoruz.

## Bağımsız oynanış testi (doğru yöntem)

- Test: `qa/cdp_test.py`.
- Kanıt: `qa/real-browser-playthrough.json`.
- Görseller: `games/seksek/screenshots/07-playthrough-after-1.png`,
  `08-playthrough-won.png`, `09-playthrough-restarted.png`,
  `10-playthrough-mobile-touch.png`.
- Test, `Input.dispatchMouseEvent` ile başlangıç ve **8 gerçek kare/ritim
  girdisi** gönderir. `__qa.snap()` yalnız **durum okumak** içindir.
  `__qa.finish()` koddan kaldırılmıştır.
- Negatif test: yanlış kareye atılınca can 3'ten 2'ye düşer.
- Mobil: `Emulation.setDeviceMetricsOverride` 390×844 ve
  `Input.dispatchTouchEvent` ile taş atma akışı doğrulanır.
- Tarayıcı konsol/runtime hatası kontrol edilir.

## Yerel yeniden üretim

Önce oyunun HTTP sunucusunu başlat:

```powershell
python -m http.server 8790 --bind 127.0.0.1 --directory games\seksek
```

Ayrı bir Edge headless örneğinde CDP 9224 portunu aç
(`--remote-debugging-port=9224 --remote-allow-origins=*`, yalnız yerel
test profilinde, ağdan erişimi açmadan). Sonra:

```powershell
python qa\cdp_test.py
python -m pytest -q games\seksek\tests\test_seksek_static.py
```

Başka portlarda test etmek için ortam değişkenleri:
`SEKSEK_BASE_URL=http://127.0.0.1:8791/`,
`SEKSEK_CDP_URL=http://127.0.0.1:9224/json/list`.

Üretim sunucusunu CDP portuyla internete açmayın.

## Sınırlar

Bu test gerçek tarayıcı olaylarıyla oyunun işleyişini doğrular fakat
insan katılımlı uzun süreli deneyim testi veya dışarıdan cihaz testi değildir.
Eski skor ekran görüntüsü değil, yeni `08-playthrough-won.png` kanıttır.
