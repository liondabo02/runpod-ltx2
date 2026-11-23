# Üslup profili ve uyarlama hattı

## 1. Üslup profili (her film aynı hareketi kullanmaz)
`tools/style_profile.py` — ön ayarlar: komedi_aile, macera, slapstick, masal, sakin_egitim.
Seçim: `AHOS_STYLE=<ad>` ortam değişkeni veya `series/<dizi>/style_profile.json` → `{"preset":"masal","override":{"dust":false}}`.
Etkisi: hareket genliği (energy), yürüyüş kişilikleri (gait), konuşma jestleri, ayak tozu/hız çizgisi, iç/dış mekân dekoru, hedef kesme süresi.
Varsayılan: komedi_aile. Referans eşleşmesi: Caillou→komedi_aile/sakin_egitim, Scooby/Şirinler→macera, Tom&Jerry→slapstick, masal kanalları→masal.

## 2. Mevcut film/çizgi filmden yeni içerik (uyarlama) — hak denetimli
Telif altındaki bir film veya çizgi filmi küçük değişiklikle çizgi film yapıp/başka sunumla yayınlamak türev eserdir ve izinsiz yapılamaz (YouTube'da telif ihlali/kanal kapatma riski). Bu yüzden:
- `adapt_source.py --mode inspire` (varsayılan): yalnız soyut yapı (perde ritmi, rol ağırlıkları, mekân türü) ve özgünleştirme kontrol listesi üretir; ad/replik/olay taşımaz.
- `--mode adapt --rights own|public_domain|licensed --proof "..."`: yalnız hakkı kanıtlı kaynak. Bilinen telifli yapım adı tespit edilirse `licensed` + yazılı lisans yoksa reddeder.
Güvenli kaynaklar: kendi videolarınız/senaryolarınız, kamu malı masallar ve eserler (ör. Kurbağa Prens, Pamuk Prenses, Kralın Yeni Giysileri gibi halk masalları), yazılı lisanslı içerik.
Komut: `python tools/adapt_source.py --source-file x.txt --out studio/adapt/x --mode inspire`
