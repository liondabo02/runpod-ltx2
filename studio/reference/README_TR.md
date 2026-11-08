# AHOS Studio-16 — Onaylanan kadro görselinin aktarımı

Bu klasör onaylanmış **toplu 2D posterin** korunması içindir. Tek kareden kesilen karakter panelleri bağımsız 3D karakter, rig, gerçek model-sheet veya onaylı çok açılı kimlik olarak değerlendirilmez.

Kullanıcı tarafından onaylanan paketin adı: `AHOS_Studio16_Onayli_Gorsel_Paketi.zip`.

ZIP, bilgisayara indirildikten sonra repo kökünde çalıştır:

```powershell
python tools/import_approved_roster_pack.py --zip "C:\Users\esmak\Downloads\AHOS_Studio16_Onayli_Gorsel_Paketi.zip"
```

Komut, içindeki poster ve 16 panelin SHA-256 değerlerini doğrular; farklı içerikle mevcut referansları **asla ezmez**. Kimlik kilitlerini ve karakter onaylarını otomatik değiştirmez. Aktarımdan sonra, referans bazlı çok açılı görsel üretimi ve ardından gerçek animasyon/rig üretimi gerekir.
