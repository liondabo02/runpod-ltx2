# Oracle Cloud ücretsiz düğüm — AHOS için uzak model

Yerel makinede RAM yetmediği için (2 GiB eşiği) kod modelini Oracle'ın
ücretsiz ARM örneğinde çalıştırıyoruz. AHOS yerelde kalır; yalnız model uzaktadır.

## 1. Örneği oluştur

Konsol: **Compute → Instances → Create**

| Alan | Değer |
|---|---|
| Ad | `AHOS-QUALITY-99` |
| Görüntü | Ubuntu 24.04 (aarch64) |
| Şekil | `VM.Standard.A1.Flex` — **2 OCPU / 12 GB** (ücretsiz kota: 4 OCPU/24 GB) |
| Bölge | Frankfurt (veya size yakın) |
| SSH anahtarı | mevcut anahtarınızı yükleyin |

**"Out of capacity" hatası** bu şekilde normaldir: ücretsiz ARM kapasitesi
bölgeye göre dalgalanır. Yapılacaklar, sırayla:

1. Birkaç dakika arayla tekrar deneyin (genelde saatler içinde açılır).
2. Aynı bölgede **farklı availability domain** seçin (AD-1/2/3).
3. Önce **1 OCPU / 6 GB** ile oluşturup sonra şekli büyütün.
4. Farklı bir bölge deneyin (ör. Amsterdam, Zürih).
5. `VM.Standard.E2.1.Micro` (AMD, 1 GB) bu iş için **yetersizdir** — model sığmaz.

## 2. Cloud-init ile Ollama

Örnek oluştururken **Show advanced options → Management → Cloud-init**
alanına `cloud-init-ollama.yaml` içeriğini yapıştırın. Kurulum ~5-10 dk sürer
(7B model ~4.7 GB indirir).

## 3. Erişim: SSH tüneli (önerilen)

11434 portunu internete **açmayın** — Ollama'da kimlik doğrulama yoktur.
Bunun yerine tünel:

```powershell
ssh -i $env:USERPROFILE\.ssh\oracle_ahos -N -L 11500:localhost:11434 ubuntu@<VM_IP>
```

Bu komut açık kaldığı sürece `http://127.0.0.1:11500` uzak modele gider.

## 4. AHOS'u uzak modele bağla

```powershell
$env:AHOS_EXECUTOR     = 'model'
$env:AHOS_LLM_BASE_URL = 'http://127.0.0.1:11500/v1'
$env:AHOS_LLM_API_KEY  = 'local-only'
$env:AHOS_LLM_MODEL    = 'qwen2.5-coder:7b'
$env:AHOS_LLM_FREE     = '1'      # sahip olunan düğüm: sıfır maliyet
```

`AHOS_LLM_FREE=1` olmadan bu adres ücretli sayılır ve reddedilir (varsayılan
kapalı politika). Yerel 2 GiB RAM kapısı yalnız `127.0.0.1:11434` + 1.5B
profilinde çalışır; tünel 11500 kullandığı için o kapıya takılmaz.

Daemon'u bu ortamla başlatın:

```powershell
.\control_plane_v2\AHOS-Daemon.ps1 -Action restart `
  -LlmBaseUrl 'http://127.0.0.1:11500/v1' -LlmFree
```

## 5. Doğrulama

```powershell
curl http://127.0.0.1:11500/api/tags          # model listesi
python -m ahos.report --runtime-dir ahos_core\runtime   # mod=model görünmeli
```

Gerçek bir görevde kanıt: `runtime/daemon-missions.jsonl` içinde
`changed_files > 0` ve QA kaydında `browser.ok`.

## Güvenlik

- 11434 genel internete kapalı; Oracle security list'te yalnız 22 (SSH) açık olsun.
- SSH anahtarı parolasız olmasın; mümkünse IP kısıtı kullanın.
- Ücretli sağlayıcı politikası değişmedi: `AHOS_ALLOW_PAID_LLM` verilmedikçe
  token başına ücretlendiren hiçbir uç kullanılmaz.
