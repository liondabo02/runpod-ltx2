# Mipiluna · Seksek — oynanabilir tek oyun

**Tür:** 2D Canvas / mobil dokunmatik mini oyun. Orijinal 8 oyunluk
`mipiluna/www/sokak-oyunlari.html` aynen korunur; bu dosyada yalnız Seksek kodu vardır.

## Başlatma

```powershell
cd C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
python -m http.server 8790 --bind 127.0.0.1 --directory games\seksek
```

**Yerel adres:** http://127.0.0.1:8790/

Bu adres yalnız sunucuyu çalıştıran aynı bilgisayarda veya o bilgisayara erişebilen
tarayıcıda açılır; internete yayımlanmış bir mağaza oyunu değildir.

## Nasıl oynanır?

1. **Başla** düğmesine bas.
2. Önce **1 numaralı kareye** dokun/tıkla. Sarı taş yaklaşık 0,35 saniyede kareye uçar.
3. Alt ritim çubuğundaki beyaz gösterge **yeşil bölgedeyken** ekrana dokun.
4. Sonraki turda **2 numaralı kareyi** hedefle. Bu sırayı **8. kareye kadar** tamamla.
5. Başarılı 8 turun sonunda **30 puan, 3 yıldız** kazanılır. **Başla** ile sıfırdan oyna.

Yanlış kare seçildiğinde veya yeşil alan kaçırıldığında can azalır; üç can biterse
başarısız olursun. Puan, süre, can, denge ve seviye arayüzde gösterilir.
Oyun; ses, öğretmen açıklaması, ipucu, mobil dokunma ve yerel ilerleme kaydını kullanır.

## Gerçek doğrulama

- Tarayıcı: Microsoft Edge, **CDP gerçek fare/touch olayları**.
- Başlat düğmesiyle giriş, sırayla 1–8 kareye tıklama, sekiz zamanlı atlayış,
  **gerçek 30 puan**, yeniden başlatma, yanlış atışta can azalması doğrulandı.
- Mobil 390×844: fiziksel dokunma olayıyla başlangıç ve 1. kareye geçiş doğrulandı.
- `__qa.finish()` gibi doğrudan kazandıran test kısayolu kaldırıldı.
- Kanıt: `qa/real-browser-playthrough.json`, `qa/cdp_test.py`,
  `games/seksek/screenshots/07-*.png`–`10-*.png`.
- Statik test: `python -m pytest -q games/seksek/tests/test_seksek_static.py`.
- JavaScript: HTML içindeki betik ayıklanıp `node --check` ile kontrol edildi.

**Kapsam sınırı:** Bu, üç boyutlu oyun değildir; 10 dakikalık insan
kullanılabilirlik testi, farklı fiziksel Android/iOS cihazları ve mağaza yayını
henüz doğrulanmadı. QA ekran görüntüleri algoritmik olayların kanıtıdır, çocuk
kullanıcı deneyimi onayı değildir.
