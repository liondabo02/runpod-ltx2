# AHOS — Oracle'da Panel + Worker dağıtımı

> Not: `ops/cloud/README.md` zaten **outbox** mimarisini anlatıyor (VM yama önerir,
> PC doğrular). Bu dosya ek olarak **panelin ve worker'ın bulutta çalışmasını**
> kurar. İki yaklaşım birlikte kullanılabilir.

## Tek komut (Windows'tan)
```powershell
cd C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
powershell -NoProfile -ExecutionPolicy Bypass -File ops\cloud\deploy-oracle.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File ops\cloud\deploy-oracle.ps1
```

Kurulan servisler:
| Servis | Ne yapar |
|---|---|
| `ahos-panel.service` | Panel 127.0.0.1:8766, systemd ile otomatik yeniden başlar |
| `ahos-worker.service` | Kuyruk tüketicisi (`ahos.daemon`, deterministik mod, 6 görev/saat) |

Erişim (panel dışarı açılmaz):
```powershell
ssh -L 8766:127.0.0.1:8766 oracle
# tarayıcı: http://127.0.0.1:8766/
```

## Model seçenekleri
1. **Ücretsiz tünel (önerilen)**: Windows'ta açık kalır, sunucuya ters tünel:
   `ssh -R 11500:127.0.0.1:11500 oracle`
2. **Sunucuda yerel Ollama**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5-coder:7b
   ```
   servis dosyasında `AHOS_LLM_BASE_URL=http://127.0.0.1:11434/v1`

## Sağlık
```bash
ssh oracle 'sudo systemctl status ahos-panel ahos-worker --no-pager'
ssh oracle 'sudo journalctl -u ahos-panel -n 100 --no-pager'
ssh oracle 'curl -fsS http://127.0.0.1:8766/api/status | head -c 200'
```

## Geri alma
```bash
ssh oracle 'sudo systemctl disable --now ahos-panel ahos-worker; \
  sudo rm -f /etc/systemd/system/ahos-panel.service /etc/systemd/system/ahos-worker.service; \
  sudo systemctl daemon-reload; sudo rm -rf /opt/ahos'
```

## Dürüst sınırlar
- `deploy-oracle.ps1` bu oturumda **çalıştırılmadı** (SSH alt süreci ajan
  sandbox'ında takılıyor). Betik kuru çalıştırma ile doğrulanabilir.
- Sunucuda `python3` gerekir (Ubuntu 24.04'te hazır).
- Ücretli model varsayılan kapalı; açmak için `AHOS_ALLOW_PAID_LLM=1` + anahtar.
- Panel yalnız localhost; dış erişim için nginx/firewall ayrı iş.
