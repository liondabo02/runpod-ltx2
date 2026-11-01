---
name: ai-platform-department
description: Yapay Zekâ Platformu üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Yapay Zekâ Platformu

Bu beceri, **Yapay Zekâ Platformu** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Holdingin yapay zekâ altyapısını yönetir: araç kataloğu, model geçidi, maliyet kontrolü ve dış platform entegrasyonları.

## Ücretsiz araç seti

- yerel model (ollama)
- edge-tts
- provider zinciri

## Beklenen çıktılar

- model karşılaştırması
- maliyet notu
- seçim gerekçesi

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
