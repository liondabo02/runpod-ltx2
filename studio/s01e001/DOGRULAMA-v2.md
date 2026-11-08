# S01E001 v2 — doğrulama kaydı

Tarih: 2026-11-08 · Dal: `feature/ahos-s01e001-script`

## Doğrulayıcı

```text
python tools/validate_s01e001_v2.py --json
```

Gözlenen çıktı:

```json
{"episode_seconds": 480, "opening_seconds": 30, "scenes": 11,
 "shots": 6, "problems": [], "ok": true}
```

Düz metin çalıştırması: `PASS`, exit 0.

## Testler

```text
python -m pytest -q tests/test_s01e001_package.py tests/test_s01e001_v2.py
13 passed in 0.55s
```

- v1 paket testleri: 6
- v2 kronoloji/açılış/Kaan dili/v1-POC koruma testleri: 7
- 0 failed.

## Not

`evidence/` dizinine bu turda yazma denemesi dosya sistemi kilidi nedeniyle
tamamlanmadı; bu nedenle sonuçlar bu dosyaya elle kaydedildi. Yukarıdaki
komutlar tekrar çalıştırılabilir.
