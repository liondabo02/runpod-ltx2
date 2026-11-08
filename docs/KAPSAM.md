# Test kapsamı (coverage)

Ölçüm: 2026-11-06 · araç: `coverage` 7.17.2 · komut: `coverage run --source=ahos -m pytest`

## Sonuç

```
TOTAL   23147 ifade   5648 kaçan   %76
17 dosya tamamen kapsanmış (raporlamada gizli)
```

Eşik: `pyproject.toml` → `[tool.coverage.report] fail_under = 70`.
Kapsam sessizce düşerse CI kırılır; eşik, ölçülen tabanın (76) biraz altında.

## En düşük kapsamlı modüller (öncelik sırası)

| Modül | İfade | Kapsam |
|---|---|---|
| `dept_improve.py` | 73 | 0% |
| `studio_process.py` | 69 | 0% |
| `development_ledger.py` | 31 | 0% |
| `document_executor.py` | 30 | 0% |
| `studio_process_job.py` | 37 | 0% |
| `tunnel.py` | 50 | 0% |
| `studio_review.py` | 50 | 0% |
| `daily_report.py` | 54 | 0% |

Bunlar çoğunlukla CLI/orkestrasyon modülleri; kritik yollar (`queue`,
`completion_db_guard`, `acceptance`, `project_qa`, `studio_qa`, `studio_2d`)
yüksek kapsamlı.

## Kapsam ölçümü neden yavaş

Enstrümantasyon 100 görevlik soak testini ~2 kat yavaşlatıyor. Bu yüzden:
- soak testinin bütçesi `AHOS_SOAK_BUDGET_SECONDS` ile ayarlanabilir (varsayılan 300 sn),
- CI'da kapsam ölçümü **ayrı adımda** ve yalnız ubuntu'da çalışır, bütçe 600 sn.

## Komutlar

```bash
cd ahos_core
coverage run --source=ahos -m pytest -q
coverage report --skip-covered
coverage html            # coverage-html/index.html
```
