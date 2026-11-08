# RunPod durumu (ölçülmüş)

Son ölçüm: 2026-11-01 21:59 (Europe/Berlin)

## Bağlantı var

`control_plane_v2/.env.runtime` içinde anahtar ve uç kimlikleri tanımlı
(değerler burada yazılmaz):

| Değişken | Durum |
|---|---|
| `RUNPOD_API_KEY` | var (50 karakter) |
| `RUNPOD_LTX2_ENDPOINT_ID` | `dnwqoolyprqr69` |
| `RUNPOD_KOKORO_ENDPOINT_ID` | `4vygp64ky68w3z` |
| `RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID` | `omcmra98poduyy` (bu anahtarla 403) |

## Doğrulanan yetenekler

| İşlem | Sonuç |
|---|---|
| `GET /v2/<ltx2>/health` | **PASS** (yanıt geldi, 200) |
| `GET /v2/<kokoro>/health` | **PASS** |
| İş gönderme (`POST /run`) | **PASS** — iş kimliği alındı |
| İş iptali (`POST /cancel/<id>`) | **PASS** — `CANCELLED` |
| Kimlik doğrulama | **PASS** (401 değil) |

Yani **API tarafı tamamen çalışıyor**; anahtar geçerli, uçlar kayıtlı,
gönderme ve iptal başarılı.

## Kapasite yok (gerçek engel)

LTX-2 ucuna gönderilen ping işi **10 dakika boyunca `IN_QUEUE`** kaldı;
hiçbir worker başlamadı. Sağlık yanıtı tüm worker sayaçlarını 0 gösteriyor:

```
workers: idle 0 · initializing 0 · ready 0 · running 0 · throttled 0
jobs:    completed 0 · failed 1 · inProgress 0 · inQueue 0
```

İş iptal edildi (`CANCELLED`) — kuyrukta asılı iş bırakılmadı.

### Olası nedenler (konsoldan bakılacak)

1. Endpoint **Paused** veya `Workers max = 0` (ölçeklenmiyor).
2. Seçili **GPU tipi stokta yok** (serverless cold start başlayamıyor).
3. **Template** başlatılamıyor — `jobs.failed: 1` bunu düşündürüyor
   (model indirme/bootstrap hatası).
4. `Qwen3` ucu **başka bir hesaba** ait (403).

## Kontrol komutu

```powershell
cd control_plane_v2
powershell -NoProfile -ExecutionPolicy Bypass -File .\Check-RunPod-LTX2-Health.ps1
```

## Konsolda düzeltme

- Endpoint → **Workers**: `Max workers` ≥ 1, `Min workers` = 0 (ya da 1).
- Endpoint → **GPU**: stokta olan tipi seç (ör. RTX 4090 / A40).
- Endpoint → **Template**: son çalıştırma hatasına bak; model bootstrap
  adımı düşüyorsa imaj etiketini güncelle.
- Düzeltildikten sonra tek ping yeterli; ardından 5 sn'lik test klibi.

## Maliyet notu

Ping işi worker başlatmadığı için GPU ücreti oluşmadı (kuyrukta bekleyen iş
ücretlendirilmez). İptal, asılı kalmasın diye yapıldı.
