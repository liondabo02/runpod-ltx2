---
name: task-observer
description: AHOS işçilerinin çalışırken sürtünmeyi, sahibin düzeltmelerini ve yeniden kullanılabilir yöntemleri gözlem dosyası olarak kaydeder; periyodik incelemeyle iyileştirme önerisine çevirir.
license: CC-BY-4.0 (kavram: rebelytics/one-skill-to-rule-them-all task-observer, Eoghan Henn ve katkıcılar; burada AHOS için uyarlanmış, kısaltılmış sürümdür)
---
# Task Observer (AHOS uyarlaması)

Kural: gözlem YAZAR, kodu/ayarı kendi başına DEĞİŞTİRMEZ. Düzeltme önerisi studio/improvements/ altına gider, sahibi onaylamadan uygulanmaz.

## Ne zaman gözlemle
- Bir işçi hata verdi / QA kalmadı / elle düzeltme gerekti
- Sahip (Harun) bir çıktıyı beğenmedi veya düzeltti
- Tekrar kullanılabilir iyi bir yöntem bulundu

## Nasıl kaydet
`python tools/task_observer.py log --worker render --kind friction --issue "..." --fix "..."`
Tür: friction | correction | method. Dosya: studio/observations/NNNN-slug.json. Aynı sorun tekrar yazılmaz (sayaç artar).

## İnceleme
`python tools/task_observer.py review` → tekrar eden (>=2) gözlemleri öneriye çevirir (studio/improvements/), ders hafızasına (lessons) yalnız METİN dersi ekler, çözülenleri archive/ klasörüne taşır.

## Yasaklar
Gizli anahtar, kişisel veri, ağ çağrısı, otomatik kod değişikliği yok.
