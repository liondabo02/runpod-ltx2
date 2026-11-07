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
| **Teslimat doğrulama işareti (`delivery.verified`)** | **1.336** |
| Roster işçi | 81 |
| **Doğrulanmış teslimat işareti ile ilişkili işçi** | **34** |
| **Teslimat işaretiyle ilişkisi gösterilemeyen işçi** | **47** |
| Teslimat doğrulama işareti görülen departman | **17 / 17** |

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


## Bağımsız dosya kanıtı kontrolü (ek doğrulama)

Canlı sistemde ayrıca `python tools/workforce_output_audit.py --verify-qa`
çalıştırılarak çalışma zamanındaki QA JSON dosyaları salt okunur denetlendi.

| Kanıt kategorisi | Sayı | Tam olarak neyi kanıtlar? |
|---|---:|---|
| `delivery.verified=true` işaretli görev | 1.336 | Yazılımın kaydettiği doğrulama bayrağı; ürün dosyası garantisi yok |
| Mevcut ve `passed=true` QA JSON kanıtı | 1.127 | QA kaydı dosya olarak bulunabildi ve olumlu işaretli |
| QA dosyasında `functional_verified=true` | 1.127 | QA kaydında işlevsel kontrol bayrağı var; kullanıcı deneyimi/ürün kalitesi otomatik garanti değil |
| QA dosya kanıtı doğrulanamayan işaretli görev | 209 | Eski doğrulama bayrağı var; fiziksel QA dosyası bulunamadı veya geçerli kanıt sunmadı |

**Çok önemli:** 1.336 veya 1.127 farklı, satılabilir, kullanıcıya teslim edilmiş
gerçek ürün sayısı **değildir**. Kaydedilmiş görev adımları ve QA kanıtları
ayrı seviyelerdir. Özellikle `qa-01` görevlisi 1.335 adet
`delivery.producer_ids` kaydında geçiyor; salt işçi dağılımı gerçek
ticari üretkenlik olarak yorumlanamaz.

Ürün seviyesinin onaylanması için teslim dosyasının varlığı, içerik hash'i,
gerçek işlevsellik, bağımsız QA ve son kullanıcı kabulü ayrı doğrulanmalıdır.
Bu turda hiçbir eksik kanıt PASS yapılmadı; veri ve medya değiştirilmedi.
