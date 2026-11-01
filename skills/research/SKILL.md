---
name: research-department
description: Araştırma Departmanı üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Araştırma Departmanı

Bu beceri, **Araştırma Departmanı** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Deliver research work for the holding within owner policy. Keywords: arastirma analiz rapor research analysis.

## Ücretsiz araç seti

- arXiv / OpenAlex / Semantic Scholar (ücretsiz API)
- Crossref DOI doğrulama
- Zotero (ücretsiz)

## Beklenen çıktılar

- araştırma sorusu
- kaynak listesi (DOI'li)
- bulgular + sınırlar

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.
