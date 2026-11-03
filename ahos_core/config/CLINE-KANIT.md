# CLINE — Kanıt Kaydı

Bu dosya, Cline'ın (ve diğer ajanların) **gerçekten çalıştırdığı** komutların kanıt kaydıdır.
Burada karşılığı olmayan hiçbir iddia geçerli değildir (bkz. `AGENTS.md` §6).

## Format
```
## <tarih saat>
komut : <tam komut>
exit  : <kod>
çıktı : <ham stdout/stderr>
kaynak: <dosya> → <alan>=<değer>
```

## 2026-11-03 21:09 — Eğitim (referans kayıt)
komut : python -c "from ahos.training import teach; ..."
exit  : 0
çıktı : departman: 17 · çalışan: 81 · geçen: 81 · kalan: 0 · ortalama: %100.0 · süre: 0.344 sn
kaynak: ahos_core/config/training-report.json → passed=81, failed=0, average_score=100.0, generated_at=2026-11-03T21:09:45

## 2026-11-03 21:33 — Sağlık denetimi
komut : python -c "from ahos.health_guard import check; print(check(Path('runtime'), fix=True).to_dict())"
exit  : 0
çıktı : genel: SORUN VAR · servis:panel TimeoutError · daemon stopped (tick 108) · ofis 200 · tünel 200
kaynak: ahos_core/config/health-report.json → ok=false
