# Aden aday model sheet & ifade sheet — üretim kaydı

Durum: **CANDIDATE_PENDING_REVIEW** · sahip onayı yok · ticari kullanım doğrulanmadı

## Üretim

| Girdi | Model | Seed | Çıktı |
|---|---|---|---|
| Kabul edilen Aden paneli | `black-forest-labs/FLUX.1-Kontext-Dev` | 1001 | 5 görünüşlü tur (ön, sol profil, arka, 3/4) |
| Aynı panel | `FLUX.1-Kontext-Dev` | 1102 | sağ profil tam vücut |
| Tur görseli | `FLUX.1-Kontext-Dev` | 1203 | 15 panelli ifade sheet |

**Prompt özeti:** aynı 3 yaş kız; yuvarlak yüz, büyük koyu kahve gözler, sol yanakta üç çil,
omuz hizası dalgalı koyu kahve saç, **tek** küçük sarı yıldız toka, kobalt mavi tişört +
sarı uçurtma baskısı, lacivert şort, krem/ayakkabı; nötr gri stüdyo; metin/filigran yok.

## Görsel değerlendirme (dürüst)

**Tutan:** aynı yüz ve saç; tek yıldız toka; üç çil görünür; kobalt tişört + uçurtma baskısı;
lacivert şort; ön/yan/arka/3-4 tutarlı; 15 ifade aynı kimlikte.

**Tutmayan / risk:**
1. **Ayakkabı:** görsellerde mavi yıldızlı spor ayakkabı; kanon "krem ayakkabı + mavi taban".
2. **Toka boyutu:** kanon "küçük" yıldız; görsellerde belirgin büyük yıldız.
3. İfade panelleri **etiketlenmedi**; hangi panelin hangi duygu olduğu insan incelemesi ister.
4. Sağ profil tek görünüş; ölçek diğer panellerle birebir değil.
5. **Lisans:** FLUX.1-Kontext-Dev **NON-COMMERCIAL**; ticari kullanım yok.

## Karar

- Bu bir **onay adayıdır**; final model sheet değil.
- `identity-lock` değiştirilmedi; `APPROVED` verilmedi.
- Ticari kullanım ve sahip onayı olmadan üretime alınmaz.

## Dosyalar

- `ADEN-model-sheet-candidate-v1.png` (1920×1090)
- `ADEN-expressions-candidate-v1.png` (15 panel)
- `model-sheet-manifest.json` — SHA-256, seed, model, lisans notu
