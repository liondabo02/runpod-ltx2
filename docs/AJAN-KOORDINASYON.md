# Ajan koordinasyonu — çakışmayı önleme

Bu depoda iki ajan paralel çalışır. Aynı dosyaya aynı anda yazmak
`git` çakışması ve yarım kalmış özellik üretir; bu yüzden dosya sahipliği
aşağıdaki gibidir.

## Dosya sahipliği

| Alan | Sahip | Kapsam |
|---|---|---|
| Çekirdek | Codex / ChatGPT | `ahos_core/ahos/*.py`, `ahos_core/tests/*.py` |
| Araçlar ve işletim | DSH oturumu | `tools/*.py`, `control_plane_v2/*.ps1`, `ahos_core/config/*` (raporlar), `runtime/*` |
| 3B ofis | DSH oturumu | `ahos_core/ahos/office_3d.py` (yalnız görsel katman) |

Kurallar:

1. **Force push yok.** `main` yalnız normal merge ile ilerler.
2. Bir ajan diğerinin sahasındaki dosyayı değiştirecekse önce o dosyada
   **commit edilmemiş değişiklik olup olmadığını** kontrol eder; varsa beklemez,
   değişikliği ayrı commit'te ve açık mesajla yapar.
3. `main`'e merge yalnızca çalışma ağacı temizken (veya yalnız kendi
   dosyaları stage'lenmişken) yapılır. Merge sonrası hızlı test:
   `python -m pytest -q ahos_core/tests/test_queue_drain.py ahos_core/tests/test_observed_learning.py`
4. Rapor/kanıt dosyaları (`ahos_core/config/improvement-trend.jsonl`,
   `plan-score-spread.json`, `runtime/*.jsonl`) sahipli değildir; her ajan
   yalnız kendi ürettiği satırı ekler, başkasının satırını silmez.

## Bu oturumda eklenen araçlar

| Araç | İş |
|---|---|
| `tools/drain_batch.py` | Kuyruğu 25'lik partilerle eritir. |
| `tools/software_file_task.py` | Var olan dosyaya görev verir; hash + geri okuma + kabul kapısı kanıtı üretir. |
| `tools/score_workers.py` | Plan puanlarını `missions.result_json.steps` kaydından tüm işçilere yayar (idempotent). |
| `tools/plan_bind.py` | Plan adımlarını tekilleştirip gerçek göreve bağlar, çalıştırır ve puanlar. |
| `tools/repair_plan_missions.py` | Yanlış rotalanmış plan görevlerini belge rotasına çevirir/tekilleştirir. |
| `tools/research_loop.py` | İş yokken bütün işçiler için sürekli internet araştırması (Wikipedia + Hacker News). |
| `control_plane_v2/AHOS-Research-Keepalive.ps1` | Araştırma döngüsünü ayakta tutar (başlat/status). |

## Kanıt kuralı

Sayı veya "çalıştı" iddiası yalnız şu üçünden biriyle verilir: gerçek komut
çıktısı, gerçek dosya hash'i, gerçek veritabanı satırı. Kaynaksız sayı geçersizdir.
