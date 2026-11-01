---
name: guvenlik-department
description: Güvenlik ve Kaynak Koruma Departmanı üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Güvenlik ve Kaynak Koruma Departmanı

Bu beceri, **Güvenlik ve Kaynak Koruma Departmanı** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Sistemin kaynak kodunu, bağımlılıklarını ve sırlarını sürekli izler; GitHub tarafındaki riskleri ve iyileştirme fırsatlarını raporlar.

## Ücretsiz araç seti

- sır taraması (git grep + entropy)
- yedek doğrulama
- erişim denetimi (kim neyi görebiliyor)

## Beklenen çıktılar

- risk kaydı
- sır envanteri
- erişim matrisi

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
