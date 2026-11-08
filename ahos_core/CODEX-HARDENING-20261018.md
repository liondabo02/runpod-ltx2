# Codex doğrudan düzeltmeler — 18 Ekim 2026

DeepSeek'e yeni komut gönderilmedi. Çalışan panel/işçi durdurulmadı.

## Uygulanan kod
- ahos/acceptance.py: QA sırasında güven kaydı oluşturma kaldırıldı. Eksik, bozuk, yanlış proje, şeması geçersiz, tekrarlı anahtarlı veya aşırı büyük güven kaydı/test reddedilir. Doğrulayıcı kayıt dosyasını değiştirmez.
- ahos/worker_runtime.py: üretim yürütücüsü bağlı değil hatası executor_unavailable koduyla, sabit ve sırları yansıtmayan sonraki adımla aktarılır.
- Kabul güveni ve QA entegrasyon testleri kaynak test dizinine eklendi; eski hash koruma testi bağımsız ön-kayıt fikstürüyle güncellendi.

## Doğrulama
31 ilgili test aday kaynakta geçti; aynı 31 test kurulu AHOS kaynaklarıyla yeniden geçti (13.14s). Üretim kodları hash karşılaştırması ve yedekle kuruldu. installed-hashes.json ve backups/ geri alma kanıtlarıdır.

## Kabul kaydı kullanımı
Bu doğrulayıcı kabul testini kendisi yetkilendirmez. Proje için aday çalıştırılmadan önce bağımsız olarak incelenmiş testin SHA-256 değeri, adayın değiştiremediği kabul kaydına yazılmış olmalıdır. Mevcut kayıt biçimi canonical gate yolu -> 64 karakter küçük harf SHA-256 haritasıdır. Bu kayıt eksikse QA engellenir; otomatik tekrar kayıt yapılmaz. Önceden oluşmuş bir hash kaydı anlamsal doğruluk veya güvenilir köken kanıtı değildir; bağımsız incelenmelidir.

## Açık kapsam
İçe aktarılan tüm test bağımlılıklarının manifesti, host kodunu izole çalıştırma, genel yürütücü için süreç sonlandırma ve gerçek çok dosyalı AI üretim kabulü bitmedi. Üretim yürütücüsü bağlı olmayan yazılım departmanı bu değişiklikle kod yazabilir hâle gelmiş sayılmaz. Otonomi paketindeki iki başarısız test önceki denetimde açık kaldı; bu dar test grubuyla kapanmış sayılmaz.

Çalışan servisler yeniden yüklenmedi; uzun yaşayan süreçlerin yeni modülleri yüklediği doğrulanmadı. Canlı görev ve panel süreçleri korunuyor. Sonraki güvenli bakımda yeniden yükleme öncesi görev/lease kontrolü yapılmalıdır.
