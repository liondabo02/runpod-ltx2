# AHOS Studio-16 — Onaylanan Kadro Görseli

Bu paket, son revizyonda kabul edilen 16 kişilik **tek bir toplu görseli**, orijinal dosyanın SHA-256 kaydını ve bu görselden **aynen kesilmiş** 16 karakter panelini içerir. Çıkarılan paneller yeni karakter resimleri veya gerçek 3D modeller **değildir**.

## Sonraki üretim aşaması
1. Orijinal poster ve panel dosyalarını AHOS projesinde değiştirilemez referans olarak sakla.
2. Her karakter için paneldeki yüzün ön/yan/3-çeyrek görünümünü referans-korumalı üretimle ayrı ayrı oluştur; onaysız varyantları kilitleme.
3. 16 referansın yüz tutarlılığını test et, eksik 3D mesh ve rig'leri üret.
4. 16 karakterin olduğu posterden tek kare animasyon yapıldığını gerçek karakter animasyonu olarak raporlama.
5. S01E001 için önce Aden-Kaan'lı kısa, gerçek hareket içeren sahne üret.

Karakterlerin yaşı ve kimliği mevcut `studio/canon` ve `studio/characters` kayıtlarından takip edilmelidir.
