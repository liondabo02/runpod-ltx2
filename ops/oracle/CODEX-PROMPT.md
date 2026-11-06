# Codex'e verilecek görev — Oracle düğümü

Aşağıdaki metni olduğu gibi Codex'e yapıştır.

---

**Görev: Oracle Cloud Free Tier üzerinde AHOS için model düğümü oluştur ve doğrula.**

Bağlam
- AHOS yerelde çalışıyor; yerel RAM yetmediği için kod modeli (qwen2.5-coder) uzakta çalışacak.
- Repo: `C:\actions-runner\_work\runpod-ltx2\runpod-ltx2`
- Cloud-init dosyası hazır: `ops\oracle\cloud-init-ollama.yaml` (Ollama + 7B model, yalnız localhost).
- `C:\Users\esmak\.ssh\ahos-quality-99` **geçersiz** (21 bayt, `.pub` yok). Önce anahtar üret.

Adımlar

1. **SSH anahtarı** (varsa yeniden kullan, yoksa üret):
   ```powershell
   ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\ahos-quality-99" -N '""' -C "ahos-quality-99"
   Get-Content "$env:USERPROFILE\.ssh\ahos-quality-99.pub"
   ```

2. **Örnek oluştur** (Oracle konsolu → Compute → Instances → Create):
   - Ad: `AHOS-QUALITY-99`
   - Görüntü: Ubuntu 24.04 (aarch64)
   - Şekil: `VM.Standard.A1.Flex`, **2 OCPU / 12 GB**
   - Bölge: Frankfurt (yakınsa Amsterdam/Zürih)
   - SSH anahtarı: 1. adımdaki `.pub` içeriği
   - Advanced → Management → Cloud-init: `ops\oracle\cloud-init-ollama.yaml` içeriğini yapıştır

3. **Kapasite hatası** (`Out of capacity`) alırsan sırayla dene, vazgeçme:
   a. Aynı bölgede 3 availability domain'i tek tek dene.
   b. Önce **1 OCPU / 6 GB** oluştur; başarılıysa şekli 2/12'ye büyüt.
   c. Farklı bölge (Amsterdam, Zürih).
   d. 2 dakika arayla en fazla 10 deneme; sonucu kaydet.

4. **Güvenlik**: 11434 portunu **internete açma**; security list'te yalnız 22 (SSH) kalsın.
   Ollama'da kimlik doğrulama yok.

5. **Doğrula** (VM açıldıktan 5-10 dk sonra):
   ```powershell
   ssh -i $env:USERPROFILE\.ssh\ahos-quality-99 ubuntu@<IP> "ollama list"
   ssh -i $env:USERPROFILE\.ssh\ahos-quality-99 ubuntu@<IP> "systemctl is-active ollama"
   ```
   Beklenen: `qwen2.5-coder:7b` listede, servis `active`.

6. **Bana döndür**: VM public IP, kullanıcı adı (`ubuntu`), anahtar yolu, `ollama list` çıktısı.
   Ücretli kaynak açma, free tier dışına çıkma, 11434'ü açma.

---

## Bana gereken (VM açılınca)

Sadece 3 bilgi: **IP**, **kullanıcı adı**, **anahtar yolu**. Sonrasını ben yaparım:

```powershell
ssh -i <anahtar> -N -L 11500:localhost:11434 ubuntu@<IP>
.\control_plane_v2\AHOS-Daemon.ps1 -Action restart `
  -LlmBaseUrl 'http://127.0.0.1:11500/v1' -LlmModel 'qwen2.5-coder:7b' -LlmFree
```

Doğrulama: `python -m ahos.report --runtime-dir ahos_core\runtime` çıktısında `mod=model`,
ardından ilk gerçek görevde `daemon-missions.jsonl` içinde `changed_files > 0`.
