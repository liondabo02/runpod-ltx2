# Kimlik kilidi (identity-lock)

16 karakterin kimlik dosyaları sürümlü ve hash-kilitlidir.

- Kaynak: `studio/characters/<id>/{character,visual-dna,color-palette,motion-profile,voice-profile,model-spec}.json`
- Kilit: `identity-lock.json` — karakter başına dosya SHA-256'ları ve bileşik `identity_sha256`.
- Doğrulama: `python tools/identity_lock.py --verify` (exit 0 = değişiklik yok).
- Değişiklik: `python tools/identity_lock.py --change <id> --reason "..."` → sürüm minor artar,
  geçmiş kaydı eklenir, **onay NONE'a döner**.

## Kritik ayrım

`LOCKED_FOR_EDIT` **onay değildir**. Hiçbir karakter `APPROVED` değildir; sahip onayı olmadan
`approval_status` yükseltilemez. Görsel referansı olmayan karakterde kilit yalnız metin/veri
kimliğini korur; görsel üretilmiş sayılmaz.

## Bilinen durum

| Alan | Durum |
|---|---|
| Kilitli karakter | 16/16 |
| Onaylı karakter | 0/16 |
| Görsel referans | 2/16 NEEDS_REVISION |
| 3D model | 0/16 |
