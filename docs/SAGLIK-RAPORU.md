# Sağlık raporu düzeltmesi — 2026-11-07

## Sorun

`health_guard.py` ofisi **8799** portunda, model tünelini **11500** portunda arıyordu.
Gerçek durum:

| Servis | Port | Ölçüm | Durum |
|---|---|---|---|
| Kontrol paneli | 8766 | HTTP **200** | zorunlu, çalışıyor |
| Ofis (gerçek) | 8801 | HTTP **200** | zorunlu, çalışıyor |
| Eski ofis | 8799 | HTTP **000** | kapalı (yanlış port) |
| Model tüneli | 11500 | HTTP **000** | isteğe bağlı, kapalı |

Eski kod, yanlış port (8799) ve kapalı tünel (11500) yüzünden **yanlış alarm** üretiyordu;
ayrıca tünel kapalıyken tüm sağlık `ok=false` oluyordu.

## Düzeltme

- `SERVICES["office"]` → `http://127.0.0.1:8801/`
- `REQUIRED_SERVICES = {"panel", "office"}`; `tunnel` **isteğe bağlı**.
- `HealthReport.ok` yalnız **zorunlu** kontrolleri dikkate alır.
- Rapor artık `warnings` alanı taşır; isteğe bağlı servis kapalıysa `ok=true` kalır,
  ama uyarı görünür. Kapalı zorunlu servis asla "çalışıyor" gösterilmez.

## Testler

```text
tests/test_health_guard.py
- office portu 8801
- tünel kapalı -> ok=true + warnings=["servis:tunnel"]
- panel kapalı -> ok=false (zorunlu)
3 passed (global + .venv)
```
