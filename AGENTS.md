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

## 6) Kanıt zorunluluğu (Cline dahil tüm ajanlar)

Bir ajan "yaptım/çalıştı/geçti" diyorsa **kanıt göstermek zorundadır**:

1. Çalıştırdığı **tam komutu** yazar
2. Hemen altına **ham stdout/stderr** yapıştırır (özet yok, kısaltma yok)
3. **exit code** yazar
4. Üretilen rapor dosyasının **`generated_at`** alanını yazar; 5 dakikadan eskiyse komutu tekrar çalıştırır
5. Komut çalışmıyorsa `ÇALIŞTIRAMADIM: <hata>` yazar ve **durur**

### Yasak ifadeler (kanıtsız kullanılırsa iddia geçersizdir)
- "based on the verified data"
- "would normally be called"
- "the system is complete"
- "shows that ... pass" (komut çıktısı olmadan)
- hafta/phase/program takvimi üretmek

### Standart komutlar
```bash
cd ahos_core
python -c "import json;from pathlib import Path;from ahos.training import teach;R=Path('runtime');b=json.loads((R/'departments.json').read_text(encoding='utf-8'));print(teach(R,b.get('departments') if isinstance(b,dict) else b))"
python -c "from pathlib import Path;from ahos.self_learning import tick,progress;R=Path('runtime');print(tick(R));print(progress(R))"
python -c "from pathlib import Path;from ahos.health_guard import check;print(check(Path('runtime'), fix=True).to_dict())"
python -m pytest -q --no-header --timeout=60 tests
```

### Kabul kriterleri (hepsi sağlanmadan "bitti" denemez)
- `config/training-report.json` → `failed = 0`, `average_score = 100`
- `config/health-report.json` → `ok = true` (panel, ofis, tünel, daemon, veritabanı)
- `pytest` → `0 failed`
- `runtime/learning/*.jsonl` → her departman için ≥ 1 kayıt

### Kanıt kaydı
Her oturumun kanıtı `ahos_core/config/CLINE-KANIT.md` dosyasına yazılır:
```
## <tarih saat>
komut : <tam komut>
exit  : <kod>
çıktı : <ham stdout>
kaynak: <dosya> → <alan>=<değer>
```
Bu dosyada karşılığı olmayan iddia **geçersizdir**.


## Sahip hedefini yürütme

SORMA, YAP. Sahip bir hedef verdiğinde: hedefi görevlere böl → kuyruğa yaz → çalıştır → raporla.
Yalnızca şunlarda sor: ücretli harcama, geri alınamaz silme, yeni hesap/anahtar.
