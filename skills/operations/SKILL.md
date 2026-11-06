---
name: operations-department
description: Operasyon Departmanı üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Operasyon Departmanı

Bu beceri, **Operasyon Departmanı** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Deliver operations work for the holding within owner policy. Keywords: operasyon planlama koordinasyon operations.

## Ücretsiz araç seti

- Task Scheduler / cron
- süreç diyagramı (Mermaid)
- RACI tablosu

## Beklenen çıktılar

- süreç adımları
- sorumluluk matrisi
- otomasyon fırsatları

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
