# Bulut işçisi — PC kapalıyken çalışma

PC kapalıyken Oracle VM saatlik olarak yama **önerileri** üretir; ürün asla
doğrudan değiştirilmez. PC açılınca yerel AHOS önerileri doğrular, geçmeyeni geri
alır.

```
VM (Oracle ARM, 12 GB)                     Yerel PC
─────────────────────                      ─────────
systemd timer (60 dk)                      Sync-AhosCloud.ps1
  └─ cloud_worker.py                         ├─ www → VM
       ├─ tasks.json                         ├─ outbox ← VM
       ├─ OpenRouter (ücretsiz model)         └─ python -m ahos.outbox
       └─ ~/ahos/outbox/*.json                     ├─ yol/find doğrulaması
                                                   ├─ tools/check_offline.py
                                                   └─ geçmezse geri al
```

## Kurulum (bir kez)

```powershell
# VM'de (yerel makineden)
scp -i <anahtar> ops/cloud/ahos-cloud-worker.service ops/cloud/ahos-cloud-worker.timer ubuntu@<IP>:/tmp/
ssh -i <anahtar> ubuntu@<IP> "sudo mv /tmp/ahos-cloud-worker.* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now ahos-cloud-worker.timer"
```

Gerekli VM dosyaları:

| Dosya | İçerik |
|---|---|
| `~/ahos_cloud_worker.py` | `ops/cloud/cloud_worker.py` |
| `~/.ahos.env` | `OPENROUTER_KEY=…`, `AHOS_MODEL=…`, `AHOS_MODELS=…` (chmod 600) |
| `~/ahos/tasks.json` | görev listesi (`ops/cloud/tasks.sample.json`) |
| `~/ahos/project/` | projenin senkron kopyası |

## Günlük kullanım

```powershell
.\ops\cloud\Sync-AhosCloud.ps1            # sadece senkron + önerileri indir
.\ops\cloud\Sync-AhosCloud.ps1 -Apply     # doğrula ve uygula
```

Sonuçlar: `quality/evidence/cloud-outbox-results.jsonl`.

## Sınırlar

- Öneriler tek tek doğrulanır; `find` tutmazsa veya `check_offline` düşerse geri alınır.
- Model küçük: bazı öneriler boş ya da eksik dosyalı çıkar (QA yakalar).
- Gizlilik: öneriler ücretsiz modele gider (OpenRouter). Istenmezse `AHOS_MODELS`
  VM'deki Ollama'ya çevrilebilir (`http://127.0.0.1:11434/v1`).
