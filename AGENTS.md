# AHOS — Ajanlar için tek doğru kaynak (Single Source of Truth)

Bu dosya, AHOS deposunda çalışan **tüm ajanlar** (Cline, Codex, Claude Code, iç ajanlar) için
bağlayıcı kuralları tanımlar.

## 1) Departman ve çalışan sayıları

- **Tek doğru kaynak:** `ahos_core/config/departments.json`
- Runtime kopyası: `ahos_core/runtime/departments.json` (git tarafından **ignore edilir**, ama diskte vardır)
- Sayım kuralı:
  - departman sayısı = `departments` dizisinin uzunluğu
  - çalışan sayısı = her departmanın `workers` dizilerinin toplamı
- **Başka hiçbir dosyadan, örnekten veya eski analizden sayı alınmaz.**

Doğrulanmış güncel değerler `ahos_core/config/system-status.json` içinde `departments` ve `workers`
alanlarındadır; bu dosya periyodik güncellenir.

## 2) Çalışma zamanı verisi

`ahos_core/runtime/` git tarafından ignore edilir. Bir ajan bu klasörü göremiyorsa:

1. Önce `ahos_core/config/` altındaki kopyalara bak (departments.json, system-status.json).
2. Gerekiyorsa mutlak yolu doğrudan oku.

## 3) Görev yürütme yolları

| Görev tipi | Yol |
|---|---|
| "dosyanın sonuna ekle / yorum ekle" | `simple_edits` (deterministik, model yok) |
| "şu metni değiştir" | `find/replace` (birebir eşleşme) |
| "yeni dosya oluştur" | whole-file yazma |
| "tasarla / bölüm ekle" | model yolu |

**Kural:** deterministik uygulanabilen bir görev modele gönderilmez.

## 4) Kabul kapısı

- `changed_files == 0` olan görev **başarılı sayılmaz** (`boş teslim` reddedilir).
- Proje bağlı görevlerde kabul kaydı `AHOS_PROJECT_QA_TRUSTED=1` ile ilk kullanımda oluşturulur (TOFU),
  sonrasında hash ile denetlenir.

## 5) Raporlama

Sayı vermeden önce **kaynağı** yaz: hangi dosya, hangi alan. Kaynaksız sayı geçersizdir.
