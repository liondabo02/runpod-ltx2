---
name: finance-department
description: Finans Departmanı üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Finans Departmanı

Bu beceri, **Finans Departmanı** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Deliver finance work for the holding within owner policy. Keywords: finans butce maliyet finance budget.

## Ücretsiz araç seti

- Python + pandas ile bütçe tablosu
- GnuCash (ücretsiz muhasebe)
- Excel/Sheets şablonu
- vergi takvimi hatırlatıcıları

## Beklenen çıktılar

- aylık nakit akışı
- gelir-gider özeti
- risk listesi

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
