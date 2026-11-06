---
name: sales-department
description: Satış Departmanı üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Satış Departmanı

Bu beceri, **Satış Departmanı** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Deliver sales work for the holding within owner policy. Keywords: satis musteri teklif sales crm.

## Ücretsiz araç seti

- SQLite tabanlı CRM-lite
- teklif şablonu
- e-posta takip scripti

## Beklenen çıktılar

- satış hunisi
- teklif taslağı
- haftalık takip listesi

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
