# Aden aday görseli — içe aktarma kutusu

Buraya **onay bekleyen** Aden adayı konur. İçe aktarma otomatik onay vermez.

## Kullanım

1. PNG veya JPEG dosyayı bu klasöre koy (ör. `aden-v1.png`).
2. Çalıştır:

```powershell
python tools/candidate_import.py --character aden --image studio/candidates/aden/inbox/aden-v1.png --source "ChatGPT" --note "ilk aday"
```

3. Kayıt `studio/candidates/aden/registry.json` ve `<sha12>.json` içine düşer.
4. Durum: **`CANDIDATE_PENDING_REVIEW`** · `owner_approval: NONE` · `final_use_allowed: false`.

## Kurallar

- Orijinal dosya değiştirilmez; kopya SHA-256 adıyla saklanır.
- `studio/identity/identity-lock.json` değişmez.
- `APPROVED` yalnız sahip onayıyla verilir; bu araç asla vermez.
- Bu klasördeki dosyalar adaydır; final model sheet değildir.

## Beklenen görsel özellikleri

Sarı yıldız toka · sol yanakta üç çil · omuz hizası dalgalı koyu kahve saç ·
kobalt mavi tişört · lacivert şort · krem ayakkabı · 3 yaş kız oranı.
