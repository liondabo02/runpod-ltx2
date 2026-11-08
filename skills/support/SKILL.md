---
name: support-department
description: Müşteri Destek Departmanı üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Müşteri Destek Departmanı

Bu beceri, **Müşteri Destek Departmanı** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Deliver support work for the holding within owner policy. Keywords: destek musteri hizmetleri support ticket.

## Ücretsiz araç seti

- SQLite ticket kuyruğu
- SSS bankası
- yanıt şablonları

## Beklenen çıktılar

- SSS
- yanıt süresi hedefi
- eskalasyon kuralı

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
