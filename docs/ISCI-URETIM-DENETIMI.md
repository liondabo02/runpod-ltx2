# İşçi üretim denetimi — 2026-11-07

Araç: `tools/workforce_output_audit.py` (salt okunur)
Rapor: `quality/evidence/workforce-output-audit-20261107.json`

## Zincir tanımı

`işçi → görev → gerçek çıktı → bağımsız QA → kayıt` zincirinde **yalnız
`delivery.verified=1`** olan görev ürün sayıldı. Düşünce, öneri, mesaj ve
sandbox notları ürün sayılmadı.

## Ölçüm (canlı DB)

| Metrik | Değer |
|---|---|
| Completed görev | 4.028 |
| Sonuç kaydı olan | 1.956 |
| **Doğrulanmış teslimat** | **1.336** |
| Roster işçi | 81 |
| **Doğrulanmış çıktısı olan işçi** | **34** |
| **Henüz kanıtsız işçi** | **47** |
| Doğrulanmış çıktısı olan departman | **17 / 17** |

En yüksek doğrulanmış çıktı: creative 579, data 569, ai-platform 26, sales 22, hukuk 21.

## Yorum

- "Kayıtlı olmak" üretim değil: 81 işçinin **47'si** henüz doğrulanmış çıktı üretmemiş.
- Departman kapsaması tam (17/17) ama derinlik dengesiz; iki departman toplamın
  büyük kısmını taşıyor.
- Bu turda **yeni sandbox görevi üretilmedi**; tekrarlı/düşük değerli iş kuyruğa
  eklenmedi. Pending 0 kaldı.
- 47 işçiye iş vermek için önce **somut, doğrulanabilir hedef** gerekir; "durum notu
  üret" sınıfı tekrar edilmemeli.

## Sonraki güvenli adım (onay/gerçek hedef gerektirir)

1. Her departman için gerçek bir teslim hedefi tanımla (dosya/rapor/kod).
2. İşçiyi o göreve ata; çıktı + bağımsız QA + kayıt zorunlu.
3. 47 işçiyi gruplar hâlinde (≤3) ilerlet; başarısızda dur.

Maliyet: **0 USD** (yalnız okuma ve yerel analiz).
